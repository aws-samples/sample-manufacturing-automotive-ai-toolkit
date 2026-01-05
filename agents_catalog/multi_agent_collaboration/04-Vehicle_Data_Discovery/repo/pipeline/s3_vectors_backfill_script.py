#!/usr/bin/env python3
"""
Tesla Fleet Discovery Studio - S3 Vectors Backfill Script
Populate S3 Vectors with 480 new scenes using trigger-based pipeline

Key Features:
- Nuclear reset of S3 Vectors (clean start)
- Copy ROS bags to trigger location (auto-starts pipeline)
- 3 concurrent scenes (matches GPU capacity)
- Continuous execution with resume capability
- No laptop dependency (designed for cloud deployment)
"""

import boto3
import json
import time
import random
import logging
import os
import signal
import sys
from datetime import datetime
from typing import List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class S3VectorsBackfillOrchestrator:
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name='us-west-2')
        self.s3vectors_client = boto3.client('s3vectors', region_name='us-west-2')
        self.stepfunctions_client = boto3.client('stepfunctions', region_name='us-west-2')

        # Configuration (UPDATED FOR COHERE/COSMOS ARCHITECTURE)
        self.s3_bucket = os.getenv('S3_BUCKET', '')
        self.ros_bag_prefix = "raw-data/ros-bags/nuscenes-oliver/compressed/"
        self.trigger_location = "raw-data/tesla-pipeline/"
        self.vector_bucket = os.getenv('VECTOR_BUCKET_NAME', '')
        self.state_machine_arn = os.getenv('STATE_MACHINE_ARN', '')

        # DUAL-INDEX ARCHITECTURE (Cohere + Cosmos)
        self.behavioral_index = "behavioral-metadata-index"  # Cohere 1536-dim
        self.visual_index = "video-similarity-index"        # Cosmos 768-dim
        self.output_prefix = "pipeline-results/"

        # Performance constraints (based on actual execution analysis)
        self.max_parallel_scenes = 1  # Sequential processing to avoid GPU conflicts
        self.scene_processing_time = 14 * 60  # 14 minutes per scene (12 min + 2 min buffer)
        self.batch_size = 1  # Process 1 scene at a time for sequential processing

        # State management for continuous operation
        self.state_file = "backfill_state.json"
        self.shutdown_requested = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, requesting graceful shutdown...")
        self.shutdown_requested = True

    def save_state(self, state: Dict):
        """Save execution state for resume capability"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {str(e)}")

    def load_state(self) -> Dict:
        """Load previous execution state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                logger.info(f"State loaded from {self.state_file}")
                return state
        except Exception as e:
            logger.error(f"Failed to load state: {str(e)}")

        # Return default state
        return {
            "nuclear_reset_completed": False,
            "scenes_selected": [],
            "scenes_completed": [],
            "scenes_failed": [],
            "current_batch": 0,
            "start_timestamp": datetime.utcnow().isoformat()
        }

    def nuclear_reset_s3_vectors(self) -> bool:
        """
        Nuclear reset of S3 Vectors - DUAL-INDEX ARCHITECTURE (Cohere + Cosmos)
        """
        logger.info("Starting NUCLEAR RESET of S3 Vectors dual-index architecture...")

        try:
            # Delete existing indices
            indices = [self.behavioral_index, self.visual_index]

            for index_name in indices:
                logger.info(f"Deleting existing {index_name} index...")
                try:
                    self.s3vectors_client.delete_index(
                        vectorBucketName=self.vector_bucket,
                        indexName=index_name
                    )
                    logger.info(f"{index_name} deleted successfully")
                    time.sleep(10)  # Brief pause between deletions
                except Exception as e:
                    if "NotFoundException" in str(e) or "ResourceNotFoundException" in str(e):
                        logger.info(f"{index_name} doesn't exist, skipping deletion")
                    else:
                        logger.error(f"Failed to delete {index_name}: {str(e)}")
                        return False

            # Wait after all deletions
            logger.info("Waiting for deletion propagation...")
            time.sleep(30)

            # CREATE INDEX 1: Behavioral Metadata (Cohere 1536-dim)
            logger.info(f"Creating new {self.behavioral_index} index (Cohere 1536-dim)...")
            self.s3vectors_client.create_index(
                vectorBucketName=self.vector_bucket,
                indexName=self.behavioral_index,
                dataType='float32',
                dimension=1536,  # Cohere embed-v4 dimensions
                distanceMetric='cosine',
                metadataConfiguration={
                    'nonFilterableMetadataKeys': [
                        'scene_id',
                        'input_type',
                        'behavioral_patterns',
                        'scenario_type',
                        'processing_timestamp'
                    ]
                }
            )
            logger.info("Behavioral metadata index created successfully")

            # CREATE INDEX 2: Video Similarity (Cosmos 768-dim)
            logger.info(f"Creating new {self.visual_index} index (Cosmos 768-dim)...")
            self.s3vectors_client.create_index(
                vectorBucketName=self.vector_bucket,
                indexName=self.visual_index,
                dataType='float32',
                dimension=768,   # Cosmos-Embed1 dimensions
                distanceMetric='cosine',
                metadataConfiguration={
                    'nonFilterableMetadataKeys': [
                        'scene_id',
                        'primary_camera',
                        'successful_cameras',
                        'total_cameras',
                        'processing_timestamp'
                    ]
                }
            )
            logger.info("Video similarity index created successfully")

            # Wait for both indices to be ready
            logger.info("Waiting for dual indices to be ready...")
            time.sleep(90)

            logger.info("NUCLEAR RESET completed successfully - Dual-index architecture ready!")
            return True

        except Exception as e:
            logger.error(f"NUCLEAR RESET failed: {str(e)}")
            return False

    def discover_available_scenes(self) -> Set[str]:
        """Discover all available ROS bag scenes"""
        logger.info("Discovering available ROS bag scenes...")

        available_scenes = set()
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.s3_bucket,
                Prefix=self.ros_bag_prefix
            )

            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Extract scene ID from filename: compressed-NuScenes-v1.0-trainval-scene-0001.bag
                        if 'scene-' in key and key.endswith('.bag'):
                            scene_part = key.split('scene-')[1]
                            scene_id = scene_part.split('.bag')[0]
                            if scene_id and scene_id.isdigit():
                                available_scenes.add(f"scene-{scene_id}")

            logger.info(f"Discovered {len(available_scenes)} available scenes")
            return available_scenes

        except Exception as e:
            logger.error(f"Failed to discover scenes: {str(e)}")
            return set()

    def identify_processed_scenes(self) -> Set[str]:
        """Identify scenes already processed by checking output folder"""
        logger.info("SEARCH: Identifying already processed scenes...")

        processed_scenes = set()
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.s3_bucket,
                Prefix=self.output_prefix,
                Delimiter="/"
            )

            for page in pages:
                if 'CommonPrefixes' in page:
                    for prefix in page['CommonPrefixes']:
                        folder_name = prefix['Prefix'].split('/')[-2]
                        if folder_name.startswith('scene-'):
                            processed_scenes.add(folder_name)

            logger.info(f"SUCCESS: Found {len(processed_scenes)} already processed scenes")
            return processed_scenes

        except Exception as e:
            logger.error(f"ERROR: Failed to identify processed scenes: {str(e)}")
            return set()

    def select_backfill_scenes(self, target_count: int, completed_scenes: List[str]) -> List[str]:
        """Select scenes for backfill processing (resume-aware)"""
        logger.info(f"TARGET: Selecting {target_count} scenes for backfill...")

        available_scenes = self.discover_available_scenes()
        processed_scenes = self.identify_processed_scenes()
        already_completed = set(completed_scenes)

        # CONTINUE FROM WHERE BACKFILL LEFT OFF: Find highest processed scene number
        def extract_scene_number_local(scene_id):
            try:
                return int(scene_id.replace('scene-', ''))
            except:
                return 0

        # Find the highest scene number that was processed
        highest_processed = 0
        for scene in processed_scenes:
            scene_num = extract_scene_number_local(scene)
            if scene_num > highest_processed:
                highest_processed = scene_num

        logger.info(f"CONTINUE: Highest processed scene found: scene-{highest_processed:04d}")
        logger.info(f"CONTINUE: Will process scenes after scene-{highest_processed:04d}")

        # Only select scenes with numbers higher than the highest processed
        filtered_available = set()
        for scene in available_scenes:
            scene_num = extract_scene_number_local(scene)
            if scene_num > highest_processed:
                filtered_available.add(scene)

        # Find unprocessed scenes that haven't been completed in this run
        unprocessed_scenes = filtered_available - already_completed

        logger.info(f"STATS: Scene Statistics:")
        logger.info(f"   Available scenes: {len(available_scenes)}")
        logger.info(f"   Already processed: {len(processed_scenes)}")
        logger.info(f"   Completed this run: {len(already_completed)}")
        logger.info(f"   Remaining unprocessed: {len(unprocessed_scenes)}")

        # Convert to list and sort numerically for sequential processing
        unprocessed_list = list(unprocessed_scenes)

        # Sort by scene number (scene-1, scene-2, ..., scene-N) for sequential processing
        def extract_scene_number(scene_id):
            try:
                return int(scene_id.replace('scene-', ''))
            except:
                return 999999  # Put invalid scene IDs at the end

        unprocessed_list.sort(key=extract_scene_number)

        if len(unprocessed_list) < target_count:
            logger.warning(f"WARNING: Only {len(unprocessed_list)} unprocessed scenes available")
            selected_scenes = unprocessed_list
        else:
            # SEQUENTIAL SELECTION: Take first N scenes (no scenes missed)
            selected_scenes = unprocessed_list[:target_count]

        logger.info(f"RANGE: Sequential processing range: {selected_scenes[0]} to {selected_scenes[-1]}" if selected_scenes else "No scenes selected")

        logger.info(f"SUCCESS: Selected {len(selected_scenes)} scenes for backfill")
        return selected_scenes

    def process_scene_batch(self, scene_batch: List[str], batch_number: int) -> Dict[str, any]:
        """Process a batch of scenes with controlled parallelism (3 concurrent)"""
        logger.info(f"PROCESSING: batch {batch_number}: {len(scene_batch)} scenes")
        logger.info(f"   Scenes: {', '.join(scene_batch)}")

        batch_start_time = time.time()
        results = {
            'batch_number': batch_number,
            'scenes_attempted': len(scene_batch),
            'scenes_successful': 0,
            'scenes_failed': 0,
            'failed_scenes': [],
            'successful_scenes': [],
            'processing_time': 0
        }

        # Process scenes with GPU-limited parallelism
        with ThreadPoolExecutor(max_workers=self.max_parallel_scenes) as executor:
            # Submit all scenes in batch
            future_to_scene = {
                executor.submit(self.process_single_scene, scene_id): scene_id
                for scene_id in scene_batch
            }

            # Collect results as they complete
            for future in as_completed(future_to_scene):
                scene_id = future_to_scene[future]

                # Check for shutdown request
                if self.shutdown_requested:
                    logger.info("SHUTDOWN: Requested, cancelling remaining scenes in batch")
                    break

                try:
                    success = future.result()
                    if success:
                        results['scenes_successful'] += 1
                        results['successful_scenes'].append(scene_id)
                        logger.info(f"SUCCESS: {scene_id} completed successfully")
                    else:
                        results['scenes_failed'] += 1
                        results['failed_scenes'].append(scene_id)
                        logger.error(f"ERROR: {scene_id} failed")

                except Exception as e:
                    results['scenes_failed'] += 1
                    results['failed_scenes'].append(scene_id)
                    logger.error(f"ERROR: {scene_id} exception: {str(e)}")

        batch_end_time = time.time()
        results['processing_time'] = batch_end_time - batch_start_time

        logger.info(f"STATS: Batch {batch_number} Results:")
        logger.info(f"   Successful: {results['scenes_successful']}")
        logger.info(f"   Failed: {results['scenes_failed']}")
        logger.info(f"   Time: {results['processing_time']:.1f} seconds")

        return results

    def process_single_scene(self, scene_id: str) -> bool:
        """
        Process single scene by copying ROS bag to trigger location
        Uses your tesla-s3-trigger-us-west-2 Lambda → Step Functions pipeline
        """
        logger.info(f"START: Processing for {scene_id}")

        try:
            # Source ROS bag location (CORRECTED path pattern based on actual S3 structure)
            scene_number = scene_id.replace('scene-', '').zfill(4)  # scene-1 → 0001
            source_key = f"{self.ros_bag_prefix}{scene_number}/compressed-NuScenes-v1.0-trainval-{scene_id}.bag"

            # Target trigger location (activates tesla-s3-trigger-us-west-2 Lambda)
            target_key = f"{self.trigger_location}compressed-NuScenes-v1.0-trainval-{scene_id}.bag"

            # Check if source ROS bag exists
            try:
                self.s3_client.head_object(Bucket=self.s3_bucket, Key=source_key)
            except self.s3_client.exceptions.NoSuchKey:
                logger.error(f"ERROR: {scene_id} source ROS bag not found: {source_key}")
                return False

            # Copy ROS bag to trigger location (this triggers your Lambda automatically)
            logger.info(f"COPYING: {scene_id} ROS bag to trigger location...")
            self.s3_client.copy_object(
                CopySource={'Bucket': self.s3_bucket, 'Key': source_key},
                Bucket=self.s3_bucket,
                Key=target_key
            )

            logger.info(f"PROCESSING: {scene_id} copied - Lambda trigger should start 6-phase pipeline")

            # Monitor pipeline completion by checking output folder
            success = self.monitor_pipeline_completion(scene_id)

            if success:
                logger.info(f"SUCCESS: {scene_id} completed successfully")
            else:
                logger.error(f"ERROR: {scene_id} failed or timed out")

            return success

        except Exception as e:
            logger.error(f"ERROR: {scene_id} processing exception: {str(e)}")
            return False

    def monitor_pipeline_completion(self, scene_id: str, timeout: int = 14*60) -> bool:
        """
        Smart monitoring: Check Step Functions status every 5 minutes with 14-minute hard limit
        If pipeline completes early, immediately move to next scene
        """
        start_time = time.time()
        check_interval = 5 * 60  # Check every 5 minutes

        logger.info(f"WAITING: Smart monitoring {scene_id} pipeline (Step Functions + 14min hard limit)...")

        while time.time() - start_time < timeout:
            # Check for shutdown request
            if self.shutdown_requested:
                logger.info(f"SHUTDOWN: Requested, stopping monitoring for {scene_id}")
                return False

            elapsed = time.time() - start_time

            try:
                # Find Step Functions execution for this scene
                executions = self.stepfunctions_client.list_executions(
                    stateMachineArn=self.state_machine_arn,
                    statusFilter='RUNNING',
                    maxResults=10
                )

                # Look for execution matching this scene (execution name contains scene_id)
                # Only consider executions started after monitoring began
                scene_execution = None
                for execution in executions.get('executions', []):
                    if scene_id in execution['name']:
                        execution_start_time = execution['startDate'].timestamp()
                        monitoring_start_time = start_time - 30  # 30 second buffer for Lambda trigger delay

                        if execution_start_time >= monitoring_start_time:
                            scene_execution = execution
                            break

                if scene_execution:
                    # Step Functions is still running
                    logger.info(f"WAITING: {scene_id} Step Functions RUNNING... ({elapsed/60:.1f} minutes elapsed)")

                else:
                    # Step Functions completed - check if successful (only executions started after monitoring began)
                    recent_executions = self.stepfunctions_client.list_executions(
                        stateMachineArn=self.state_machine_arn,
                        maxResults=20
                    )

                    for execution in recent_executions.get('executions', []):
                        if scene_id in execution['name']:
                            # Check if execution started AFTER we began monitoring (not old executions)
                            execution_start_time = execution['startDate'].timestamp()
                            monitoring_start_time = start_time - 30  # 30 second buffer for Lambda trigger delay

                            if execution_start_time >= monitoring_start_time:
                                status = execution['status']
                                if status == 'SUCCEEDED':
                                    logger.info(f"SUCCESS: {scene_id} Step Functions SUCCEEDED in {elapsed:.1f} seconds")
                                    return True
                                else:
                                    logger.error(f"ERROR: {scene_id} Step Functions {status} in {elapsed:.1f} seconds")
                                    return False

                    # No execution found - might be starting up
                    logger.info(f"WAITING: {scene_id} Step Functions starting... ({elapsed/60:.1f} minutes elapsed)")

            except Exception as e:
                logger.warning(f"WARNING: {scene_id} Step Functions check failed: {str(e)}")
                logger.info(f"WAITING: {scene_id} continuing to wait... ({elapsed/60:.1f} minutes elapsed)")

            # Wait for next check (or until timeout)
            remaining_time = timeout - elapsed
            wait_time = min(check_interval, remaining_time)

            if wait_time > 0:
                time.sleep(wait_time)

        # Hard timeout reached
        elapsed = time.time() - start_time
        logger.error(f"TIMEOUT: {scene_id} hard timeout after {elapsed:.1f} seconds (14 minutes)")
        return False

    def execute_backfill(self, target_scenes: int = 480) -> Dict[str, any]:
        """
        Execute the complete S3 Vectors backfill process with resume capability
        """
        logger.info(f"PROCESSING: Starting S3 Vectors backfill for {target_scenes} scenes")

        execution_start = time.time()

        # Load previous state (for resume capability)
        state = self.load_state()

        overall_results = {
            'target_scenes': target_scenes,
            'total_successful': len(state.get('scenes_completed', [])),
            'total_failed': len(state.get('scenes_failed', [])),
            'failed_scenes': state.get('scenes_failed', []),
            'successful_scenes': state.get('scenes_completed', []),
            'batch_results': [],
            'total_execution_time': 0,
            'nuclear_reset_performed': state.get('nuclear_reset_completed', False),
            'resumed_from_state': bool(state.get('scenes_completed') or state.get('scenes_failed'))
        }

        try:
            # Step 1: Nuclear reset S3 Vectors (COMMENTED OUT - PRESERVE EXISTING VECTORS)
            # if not state.get('nuclear_reset_completed', False) and not overall_results.get('resumed_from_state', False):
            #     if not self.nuclear_reset_s3_vectors():
            #         logger.error("ERROR: Nuclear reset failed, aborting backfill")
            #         return overall_results
            #
            #     state['nuclear_reset_completed'] = True
            #     overall_results['nuclear_reset_performed'] = True
            #     self.save_state(state)

            # SKIP NUCLEAR RESET - Continue processing with existing vectors
            logger.info("SKIP: Nuclear reset disabled - preserving existing S3 Vectors")
            state['nuclear_reset_completed'] = True  # Mark as completed to continue
            overall_results['nuclear_reset_performed'] = False

            # Step 2: Select scenes for backfill (resume-aware)
            if not state.get('scenes_selected'):
                selected_scenes = self.select_backfill_scenes(target_scenes, state.get('scenes_completed', []))
                state['scenes_selected'] = selected_scenes
                self.save_state(state)
            else:
                selected_scenes = state['scenes_selected']
                logger.info(f"RESUME: With {len(selected_scenes)} previously selected scenes")

            if not selected_scenes:
                logger.error("ERROR: No scenes selected for backfill")
                return overall_results

            # Step 3: Process scenes in batches (resume from current batch)
            remaining_scenes = [s for s in selected_scenes if s not in state.get('scenes_completed', []) and s not in state.get('scenes_failed', [])]

            if not remaining_scenes:
                logger.info("COMPLETE: All scenes already processed!")
                return overall_results

            total_batches = (len(remaining_scenes) + self.batch_size - 1) // self.batch_size
            start_batch = state.get('current_batch', 0)

            logger.info(f"BATCH: Processing {len(remaining_scenes)} remaining scenes in {total_batches} batches")

            for batch_num in range(start_batch, total_batches):
                if self.shutdown_requested:
                    logger.info("SHUTDOWN: Graceful shutdown requested, stopping execution")
                    break

                start_idx = batch_num * self.batch_size
                end_idx = min(start_idx + self.batch_size, len(remaining_scenes))
                batch_scenes = remaining_scenes[start_idx:end_idx]

                logger.info(f"TARGET: Starting batch {batch_num + 1} of {total_batches}")

                batch_result = self.process_scene_batch(batch_scenes, batch_num + 1)
                overall_results['batch_results'].append(batch_result)

                # Update state with results
                state['scenes_completed'].extend(batch_result['successful_scenes'])
                state['scenes_failed'].extend(batch_result['failed_scenes'])
                state['current_batch'] = batch_num + 1

                overall_results['total_successful'] = len(state['scenes_completed'])
                overall_results['total_failed'] = len(state['scenes_failed'])
                overall_results['successful_scenes'] = state['scenes_completed']
                overall_results['failed_scenes'] = state['scenes_failed']

                # Save state after each batch
                self.save_state(state)

                # Brief pause between batches (unless shutdown requested)
                if batch_num < total_batches - 1 and not self.shutdown_requested:
                    logger.info("PAUSE: Brief pause between batches...")
                    time.sleep(60)

        except Exception as e:
            logger.error(f"ERROR: Backfill execution failed: {str(e)}")

        finally:
            execution_end = time.time()
            overall_results['total_execution_time'] = execution_end - execution_start

            # Final summary
            logger.info("SUMMARY: BACKFILL EXECUTION SUMMARY")
            logger.info("=" * 50)
            logger.info(f"Target scenes: {overall_results['target_scenes']}")
            logger.info(f"Successful: {overall_results['total_successful']}")
            logger.info(f"Failed: {overall_results['total_failed']}")
            total_scenes = len(state.get('scenes_selected', []))
            if total_scenes > 0:
                success_rate = (overall_results['total_successful'] / total_scenes * 100)
                logger.info(f"Success rate: {success_rate:.1f}%")
            else:
                logger.info("Success rate: N/A (no scenes selected)")
            logger.info(f"Total time: {overall_results['total_execution_time'] / 3600:.1f} hours")
            logger.info(f"Nuclear reset: {'SUCCESS: Yes' if overall_results['nuclear_reset_performed'] else 'ERROR: No'}")

            # Save final results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = f"s3_vectors_backfill_results_{timestamp}.json"

            try:
                with open(results_file, 'w') as f:
                    json.dump(overall_results, f, indent=2)
                logger.info(f"SAVED: Final results saved to: {results_file}")
            except Exception as e:
                logger.error(f"ERROR: Failed to save final results: {str(e)}")

        return overall_results

def main():
    """Main execution function with continuous operation support"""

    # Initialize orchestrator
    orchestrator = S3VectorsBackfillOrchestrator()

    logger.info("Fleet Discovery Studio - S3 Vectors Backfill Script")
    logger.info("TARGET: 836 total scenes (continuing from scene-641 onward)")
    logger.info("CONFIG: Constraints: Sequential processing, trigger-based pipeline")
    logger.info("RESUME: Resume capability: Enabled")
    logger.info("VECTORS: Nuclear reset DISABLED - preserving existing embeddings")

    # Execute backfill with resume capability - CONTINUE FROM SCENE 641 ONWARD
    # Total dataset: 836 scenes (641-1110 + 9997-9998), Already processed: 480 scenes
    results = orchestrator.execute_backfill(target_scenes=836)

    # Success assessment
    success_rate = (results['total_successful'] / results['target_scenes'] * 100) if results['target_scenes'] > 0 else 0

    if success_rate >= 80:
        logger.info("COMPLETE: BACKFILL SUCCESSFUL - S3 Vectors cold start problem solved!")
    else:
        logger.warning(f"WARNING: BACKFILL PARTIAL SUCCESS ({success_rate:.1f}%) - Review failed scenes")

    return results

if __name__ == "__main__":
    try:
        results = main()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("INTERRUPT: Backfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"ERROR: Backfill failed with exception: {str(e)}")
        sys.exit(1)