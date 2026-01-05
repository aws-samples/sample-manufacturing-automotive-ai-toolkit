#!/usr/bin/env python3
"""
Fleet Discovery Studio - Tesla S3 Vectors Behavioral Embeddings (Phase 4-5)
Production-grade implementation with Titan embeddings generation and separation of concerns.
"""

import os
import sys
import json
import boto3
import logging
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global AWS clients for performance
s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-west-2')  # Added region for Cohere access
s3vectors_client = boto3.client('s3vectors')

# ============================================================================
# Helper Functions for Camera-Specific ID Processing
# ============================================================================

def extract_scene_from_id(camera_id: str) -> str:
    """
    Extract scene ID from camera-specific ID.

    Args:
        camera_id: Camera-specific ID like "scene_0123_CAM_FRONT"

    Returns:
        Scene ID like "scene_0123"

    Example:
        extract_scene_from_id("scene_0123_CAM_FRONT") -> "scene_0123"
    """
    if "_CAM_" in camera_id:
        # Split on last occurrence of "_CAM_" to handle scene IDs with underscores
        return camera_id.rsplit("_CAM_", 1)[0]
    else:
        logger.warning(f"Invalid camera ID format: {camera_id}")
        return camera_id  # Return as-is if format is unexpected

def extract_camera_from_id(camera_id: str) -> str:
    """
    Extract camera name from camera-specific ID.

    Args:
        camera_id: Camera-specific ID like "scene_0123_CAM_FRONT"

    Returns:
        Camera name like "CAM_FRONT"

    Example:
        extract_camera_from_id("scene_0123_CAM_FRONT") -> "CAM_FRONT"
    """
    if "_CAM_" in camera_id:
        # Extract everything after the last "_CAM_"
        return "CAM_" + camera_id.rsplit("_CAM_", 1)[1]
    else:
        logger.warning(f"Invalid camera ID format: {camera_id}")
        return "UNKNOWN_CAMERA"

def parse_camera_specific_results(s3_vectors_results: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group S3 Vectors camera-specific results by scene ID.

    Args:
        s3_vectors_results: List of S3 Vectors results with camera-specific keys

    Returns:
        Dictionary grouped by scene ID with camera information

    Example:
        Input: [{"id": "scene_0123_CAM_FRONT", "distance": 0.1}, ...]
        Output: {
            "scene_0123": [
                {"camera": "CAM_FRONT", "distance": 0.1, "camera_id": "scene_0123_CAM_FRONT"},
                {"camera": "CAM_LEFT", "distance": 0.2, "camera_id": "scene_0123_CAM_LEFT"}
            ]
        }
    """
    scene_groups = {}

    for result in s3_vectors_results:
        camera_id = result.get("id", "")
        scene_id = extract_scene_from_id(camera_id)
        camera_name = extract_camera_from_id(camera_id)

        if scene_id not in scene_groups:
            scene_groups[scene_id] = []

        # Add camera-specific result to scene group
        camera_result = {
            "camera": camera_name,
            "camera_id": camera_id,
            "distance": result.get("distance", 1.0),
            "metadata": result.get("metadata", {})
        }
        scene_groups[scene_id].append(camera_result)

    return scene_groups

def extract_structured_behavioral_features(behavioral_analysis: Dict[str, Any]) -> str:
    """
    Extract structured behavioral features from Phase 3 analysis for Cohere embedding

    Args:
        behavioral_analysis: Complete Phase 3 behavioral analysis

    Returns:
        Structured text string suitable for Cohere embedding (1536-dim)
    """
    try:
        # Get scene description from Phase 3
        scene_description = ""
        behavioral_insights = behavioral_analysis.get('behavioral_insights', {})

        if isinstance(behavioral_insights, dict):
            scene_description = behavioral_insights.get('scene_description', '')

        # Extract structured features using existing business intelligence
        business_intel = extract_business_intelligence_metadata(behavioral_analysis)

        # Create structured feature string for Cohere
        features = []

        # Add environmental context
        if business_intel.get('environment_type') != 'unknown':
            features.append(f"environment {business_intel['environment_type']}")

        # Add scenario information
        if business_intel.get('scenario_type') != 'unknown':
            features.append(f"scenario {business_intel['scenario_type']}")

        # Add safety level
        if business_intel.get('safety_criticality') != 'unknown':
            features.append(f"safety {business_intel['safety_criticality']}")

        # Extract key behavioral keywords from scene description
        if scene_description:
            behavioral_keywords = extract_behavioral_keywords(scene_description)
            features.extend(behavioral_keywords)

        # Join all features
        structured_text = " ".join(features) if features else "general driving scenario"

        logger.info(f"Extracted structured features: {structured_text[:100]}...")
        return structured_text

    except Exception as e:
        logger.error(f"Failed to extract structured features: {str(e)}")
        return "general driving scenario"

def extract_behavioral_keywords(scene_description: str) -> List[str]:
    """Extract key behavioral keywords from scene description"""
    keywords = []
    text_lower = scene_description.lower()

    # Behavioral patterns
    if any(word in text_lower for word in ['construction', 'work zone', 'barriers']):
        keywords.append('construction zone')
    if any(word in text_lower for word in ['pedestrian', 'crosswalk', 'walking']):
        keywords.append('pedestrian interaction')
    if any(word in text_lower for word in ['lane change', 'merging', 'changing lanes']):
        keywords.append('lane change')
    if any(word in text_lower for word in ['intersection', 'turning', 'traffic light']):
        keywords.append('intersection')
    if any(word in text_lower for word in ['following', 'behind', 'distance']):
        keywords.append('following behavior')
    if any(word in text_lower for word in ['speed', 'slow', 'accelerat', 'brake']):
        keywords.append('speed change')

    return keywords

def generate_cohere_embedding(text: str) -> List[float]:
    """
    Generate Cohere embedding for structured behavioral text

    Args:
        text: Structured behavioral feature text

    Returns:
        1536-dimensional Cohere embedding vector (correct dimensions)
    """
    try:
        logger.info(f"Generating Cohere embedding for: {text[:50]}...")

        response = bedrock_client.invoke_model(
            modelId="us.cohere.embed-v4:0",
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                "texts": [text],
                "input_type": "search_document",
                "embedding_types": ["float"],
                "truncate": "NONE"  # Ensures full 1536 dimensions
            })
        )

        response_body = json.loads(response['body'].read())
        embedding_vector = response_body['embeddings']['float'][0]

        # Safer embedding vector handling (prevents format change bugs)
        if isinstance(embedding_vector, list):
            # It's already a list, just ensure floats
            embedding_vector_f32 = [float(x) for x in embedding_vector]
        else:
            # It's a numpy array or other iterable
            embedding_vector_f32 = np.array(embedding_vector, dtype=np.float32).tolist()

        logger.info(f"Generated Cohere embedding: {len(embedding_vector_f32)} dimensions")
        return embedding_vector_f32

    except Exception as e:
        logger.error(f"Failed to generate Cohere embedding: {str(e)}")
        return None

def main():
    """AWS orchestration handler - manages Step Functions callback pattern"""
    task_token = None

    try:
        # Retrieve Step Functions task token
        task_token = os.getenv('STEP_FUNCTIONS_TASK_TOKEN')
        if not task_token:
            raise ValueError("STEP_FUNCTIONS_TASK_TOKEN environment variable is required")

        # Get environment variables
        scene_id = os.getenv('SCENE_ID')
        input_s3_key = os.getenv('INPUT_S3_KEY')  # Points to Phase 3 claude_analysis.json
        output_s3_key = os.getenv('OUTPUT_S3_KEY')
        s3_bucket = os.getenv('S3_BUCKET', '')

        # S3 Vectors configuration
        vector_bucket_name = os.getenv('VECTOR_BUCKET_NAME', '')
        vector_index_name = os.getenv('VECTOR_INDEX_NAME', 'behavioral-metadata-index')

        if not all([scene_id, input_s3_key, output_s3_key]):
            raise ValueError("Required environment variables: SCENE_ID, INPUT_S3_KEY, OUTPUT_S3_KEY")

        logger.info(f"Starting embeddings generation and S3 Vectors integration for scene: {scene_id}")

        # AWS Handler: Download Phase 3 Claude analysis results from S3
        local_phase3_path = f"/tmp/{scene_id}_phase3_output.json"
        logger.info(f"Downloading Phase 3 Claude analysis results...")

        # Handle S3 URI format from Phase 3 callback
        if input_s3_key.startswith('s3://'):
            bucket_name = input_s3_key.split('/')[2]
            key_name = '/'.join(input_s3_key.split('/')[3:])
        else:
            bucket_name = s3_bucket
            key_name = input_s3_key

        s3_client.download_file(bucket_name, key_name, local_phase3_path)

        # Parse Phase 3 JSON to get Claude analysis
        with open(local_phase3_path, 'r') as f:
            phase3_data = json.load(f)

        behavioral_analysis = phase3_data.get('behavioral_analysis')
        if not behavioral_analysis:
            raise ValueError("Phase 3 output missing behavioral analysis")

        logger.info(f"Found behavioral analysis with {len(behavioral_analysis.get('insights', []))} insights")

        # PURE BUSINESS LOGIC: Generate embeddings (no AWS dependencies)
        embeddings_results = generate_behavioral_embeddings(
            phase3_data, scene_id
        )

        # AWS Handler: Index embeddings in S3 Vectors
        s3_vectors_results = index_embeddings_in_s3_vectors(
            embeddings_results["s3_vectors_records"], vector_bucket_name, vector_index_name, scene_id
        )

        # AWS Handler: Upload embeddings results to S3
        output_data = {
            "scene_id": scene_id,
            "phase3_input": input_s3_key,
            "embeddings_timestamp": datetime.utcnow().isoformat(),
            "vector_bucket": vector_bucket_name,

            # --- CRITICAL FIX: EXPOSE MULTI-MODEL DATA ---
            "multi_model_architecture": True,
            "multi_model_embeddings": embeddings_results.get("multi_model_embeddings", {}),
            # ---------------------------------------------

            "vector_index": vector_index_name,
            "embeddings_vectors": embeddings_results["embeddings_vectors"],
            "embedding_metadata": embeddings_results["embedding_metadata"],
            "behavioral_metrics": embeddings_results["behavioral_metrics"],
            "s3_vectors_integration": s3_vectors_results,
            "processing_summary": {
                # Fix: Use the total count from the summary, not just the length of the legacy list
                "total_embeddings": embeddings_results["processing_summary"]["total_embeddings"],
                "successful_generations": embeddings_results["processing_summary"]["successful_generations"],
                "failed_generations": embeddings_results["processing_summary"]["failed_generations"],
                "vectors_indexed": s3_vectors_results["vectors_stored"]
            }
        }

        s3_client.put_object(
            Bucket=s3_bucket,
            Key=output_s3_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        # AWS Handler: Verify output exists
        verify_s3_output_exists(s3_bucket, output_s3_key)

        # AWS Handler: Report success to Step Functions
        success_payload = {
            "output_s3_key": output_s3_key,
            "s3_uri": f"s3://{s3_bucket}/{output_s3_key}",
            "scene_id": scene_id,
            "embeddings_summary": {
                "vectors_generated": embeddings_results["processing_summary"]["total_embeddings"],
                "vectors_indexed": s3_vectors_results["vectors_stored"],
                "indices_updated": s3_vectors_results.get("indices_used", []), # Prove we hit all 3 indices
                "total_dimensions": embeddings_results["embedding_metadata"]["dimensions"],
                "embedding_model": "multi_model (Titan+Cohere+Cosmos)",
                "vector_bucket": vector_bucket_name,
                "vector_index": vector_index_name
            },
            "timestamp": datetime.utcnow().isoformat(),
            "status": "SUCCESS"
        }

        sfn_client.send_task_success(
            taskToken=task_token,
            output=json.dumps(success_payload)
        )

        # Cleanup: Remove local files
        os.remove(local_phase3_path)
        logger.info(f"Phase 4-5 completed successfully")

    except Exception as e:
        logger.error(f"Phase 4-5 failed: {str(e)}")

        # AWS Handler: Report failure to Step Functions
        if task_token:
            try:
                sfn_client.send_task_failure(
                    taskToken=task_token,
                    error="Phase4-5.EmbeddingsGenerationFailed",
                    cause=f"Embeddings generation and S3 Vectors integration failed: {str(e)}"
                )
            except Exception as callback_error:
                logger.error(f"Failed to send callback: {str(callback_error)}")

        sys.exit(1)


def generate_behavioral_embeddings(phase3_data: Dict[str, Any], scene_id: str) -> Dict[str, Any]:
    """
    THREE-INDEX ARCHITECTURE: Generate embeddings for Titan + Cohere + Cosmos indices

    Args:
        phase3_data: Phase 3 analysis with Cosmos embeddings and behavioral text
        scene_id: Scene identifier

    Returns:
        Dictionary with three sets of embedding vectors and metadata for separate indices
    """
    logger.info(f"Generating behavioral embeddings for THREE indices (scene: {scene_id})")

    # Extract behavioral analysis components for embedding
    behavioral_analysis = phase3_data.get('behavioral_analysis', {})

    # ============================================================================
    # PRIMARY COHERE SYSTEM (Behavioral metadata embeddings)
    # ============================================================================
    logger.info("Generating Cohere embeddings for behavioral metadata...")

    # Prepare text inputs for embedding generation (similar to previous Titan logic)
    embedding_inputs = prepare_embedding_inputs(behavioral_analysis, scene_id)

    # Generate embeddings using Cohere instead of Titan
    cohere_embeddings = []
    cohere_s3_records = []
    cohere_metadata = {
        "model_id": "us.cohere.embed-v4:0",
        "dimensions": 1536,
        "processing_method": "cohere_embed_v4_1536"
    }

    for input_item in embedding_inputs:
        try:
            # Call Bedrock Cohere Embeddings model
            response = bedrock_client.invoke_model(
                modelId=cohere_metadata["model_id"],
                contentType='application/json',
                accept='application/json',
                body=json.dumps({
                    "texts": [input_item["text"]],
                    "input_type": "search_document",
                    "embedding_types": ["float"],
                    "truncate": "NONE"  # SUCCESS: Ensures full 1536 dimensions, prevents truncation errors
                })
            )

            # Parse Cohere embeddings response
            response_body = json.loads(response['body'].read())
            embedding_vector = response_body['embeddings']['float'][0]  # SUCCESS: Match working structured embedding format

            # Convert to numpy float32 for S3 Vectors compatibility
            embedding_vector_f32 = np.array(embedding_vector, dtype=np.float32).tolist()

            cohere_embeddings.append({
                "input_type": input_item["type"],
                "input_id": input_item["id"],
                "text_content": input_item["text"],
                "vector": embedding_vector_f32,
                "dimensions": len(embedding_vector_f32)
            })

            # Extract business intelligence metadata from Phase 3 analysis
            business_intelligence = extract_business_intelligence_metadata(behavioral_analysis)

            # Prepare S3 Vectors records for handler to index with enhanced metadata
            metadata = {
                "scene_id": scene_id,
                "input_type": input_item["type"],
                "input_id": input_item["id"],
                "text_preview": input_item["text"][:1500] + "..." if len(input_item["text"]) > 1500 else input_item["text"],
                "timestamp": datetime.utcnow().isoformat(),
                "embedding_model": cohere_metadata["model_id"]
            }

            # Add business intelligence metadata for HIL queries
            metadata.update(business_intelligence)

            cohere_s3_records.append({
                "key": f"{scene_id}_{input_item['id']}",
                "data": {"float32": embedding_vector_f32},
                "metadata": metadata
            })

            logger.info(f"Generated Cohere embedding for {input_item['type']}: {len(embedding_vector_f32)} dimensions")

        except Exception as e:
            logger.error(f"Failed to generate Cohere embedding for {input_item['type']}: {str(e)}")
            continue

    # ============================================================================
    # STRUCTURED COHERE FEATURES (Additional behavioral metadata)
    # ============================================================================
    logger.info("Generating additional Cohere embeddings for structured features...")

    try:
        # Extract structured behavioral features for Cohere
        structured_features = extract_structured_behavioral_features(behavioral_analysis)

        # Generate Cohere embedding
        cohere_embedding_vector = generate_cohere_embedding(structured_features)

        if cohere_embedding_vector:
            # Prepare Cohere S3 Vectors records
            business_intelligence = extract_business_intelligence_metadata(behavioral_analysis)

            cohere_metadata_record = {
                "scene_id": scene_id,
                "input_type": "structured_behavioral_features",
                "structured_features": structured_features[:500],  # Truncated for metadata
                "timestamp": datetime.utcnow().isoformat(),
                "embedding_model": "us.cohere.embed-v4:0",
                "dimensions": len(cohere_embedding_vector)  # Dynamic dimensions (not hardcoded)
            }
            cohere_metadata_record.update(business_intelligence)

            cohere_s3_records.append({
                "key": f"{scene_id}_cohere_behavioral",
                "data": {"float32": cohere_embedding_vector},
                "metadata": cohere_metadata_record,
                "target_index": "behavioral-metadata-index"  # NEW INDEX
            })

            logger.info(f"Generated Cohere embedding: {len(cohere_embedding_vector)} dimensions")
        else:
            logger.warning("Failed to generate Cohere embedding")

    except Exception as e:
        logger.error(f"Failed to generate Cohere embeddings: {str(e)}")

    # ============================================================================
    # INDEX 3: NEW COSMOS SYSTEM (Video embeddings from Phase 3)
    # ============================================================================
    logger.info("Processing Cosmos embeddings from Phase 3...")
    cosmos_s3_records = []

    try:
        # Extract Cosmos embeddings from Phase 3 output (updated for individual camera architecture)
        cosmos_data = phase3_data.get('cosmos_embeddings', {})
        per_camera_embeddings = cosmos_data.get('per_camera_embeddings', {})

        if per_camera_embeddings:
            # Process each camera embedding separately
            for camera_specific_id, embedding_data in per_camera_embeddings.items():
                if embedding_data and embedding_data.get('embedding'):
                    # Convert to float32 for consistency
                    cosmos_vector_f32 = [float(x) for x in embedding_data['embedding']]

                    # Extract camera information from Phase 3
                    camera_name = embedding_data.get('camera_name', 'UNKNOWN')
                    video_uri = embedding_data.get('video_uri', 'unknown')

                    # Prepare Cosmos S3 Vectors records for each camera
                    business_intelligence = extract_business_intelligence_metadata(behavioral_analysis)

                    cosmos_metadata_record = {
                        "scene_id": scene_id,
                        "camera_id": camera_specific_id,  # e.g., "scene_0123_CAM_FRONT"
                        "camera_name": camera_name,       # e.g., "CAM_FRONT"
                        "video_uri": video_uri,           # Original S3 video URI
                        "input_type": "video_frames",
                        "successful_cameras": cosmos_data.get('successful_embeddings', 0),
                        "total_cameras": cosmos_data.get('total_cameras', 0),
                        "timestamp": datetime.utcnow().isoformat(),
                        "embedding_model": "nvidia/Cosmos-Embed1-448p",
                        "dimensions": len(cosmos_vector_f32)
                    }
                    cosmos_metadata_record.update(business_intelligence)

                    cosmos_s3_records.append({
                        "key": camera_specific_id,  # Use camera-specific ID as key
                        "data": {"float32": cosmos_vector_f32},
                        "metadata": cosmos_metadata_record,
                        "target_index": "video-similarity-index"  # All cameras go to same index
                    })

                    logger.info(f"Processed Cosmos embedding for {camera_name}: {len(cosmos_vector_f32)} dimensions")

            logger.info(f"Processed {len(cosmos_s3_records)} camera embeddings total")
        else:
            logger.warning("No per-camera embeddings found in Phase 3 output")

    except Exception as e:
        logger.error(f"Failed to process Cosmos embeddings: {str(e)}")

    # ============================================================================
    # CONSOLIDATE RECORDS FOR INDEXER (Flat List with target_index)
    # ============================================================================

    # 1. Label Cohere Records - add target_index to records
    for record in cohere_s3_records:
        record["target_index"] = "behavioral-metadata-index"
        # Update dimensions dynamically (not hardcoded)
        if "metadata" in record and "data" in record:
            record["metadata"]["dimensions"] = len(record["data"]["float32"])

    # 2. Combine all records into one master list for indexer (Cohere + Cosmos only)
    all_records = cohere_s3_records + cosmos_s3_records

    # Generate behavioral metrics from embeddings (using Cohere instead of Titan)
    behavioral_metrics = calculate_behavioral_metrics(cohere_embeddings, behavioral_analysis)

    logger.info(f"TWO-INDEX GENERATION COMPLETE:")
    logger.info(f"  - Cohere: {len(cohere_s3_records)} embeddings → behavioral-metadata-index")
    logger.info(f"  - Cosmos: {len(cosmos_s3_records)} embeddings → video-similarity-index")

    # Prepare multi-model embedding metadata
    cohere_metadata = {
        "model_id": "us.cohere.embed-v4:0",
        "dimensions": 1536,  # Force 1536 dimensions
        "processing_method": "cohere_embed_v4_1536"
    }

    cosmos_metadata = {
        "model_id": "nvidia/Cosmos-Embed1-448p",
        "dimensions": 768,
        "processing_method": "cosmos_embed1_video"
    }

    return {
        # This single flat list contains everything needed for the multi-index write
        "s3_vectors_records": all_records,

        # NEW: Dual-model structured output for agents and results (Cohere + Cosmos)
        "multi_model_embeddings": {
            "cohere": {
                "embeddings": cohere_embeddings,
                "metadata": cohere_metadata,
                "s3_records": cohere_s3_records,
                "target_index": "behavioral-metadata-index"
            },
            "cosmos": {
                "embeddings": cosmos_s3_records,
                "metadata": cosmos_metadata,
                "s3_records": cosmos_s3_records,
                "target_index": "video-similarity-index"
            }
        },

        # Legacy fields for backward compatibility (using Cohere instead of Titan)
        "embeddings_vectors": cohere_embeddings,
        "embedding_metadata": cohere_metadata,
        "behavioral_metrics": behavioral_metrics,

        "processing_summary": {
            "total_embeddings": len(all_records),
            "cohere_count": len(cohere_s3_records),
            "cosmos_count": len(cosmos_s3_records),
            "successful_generations": len(cohere_embeddings),
            "failed_generations": len(embedding_inputs) - len(cohere_embeddings),
            "multi_model_architecture": True,
            "architecture_status": "dual_model_active"
        }
    }


def index_embeddings_in_s3_vectors(vectors_records: List[Dict[str, Any]],
                                 vector_bucket_name: str, vector_index_name: str,
                                 scene_id: str) -> Dict[str, Any]:
    """
    Index embedding vectors in S3 Vectors using PutVectors API (Multi-Index Support)

    Enhanced to support dual-index architecture with target_index routing:
    - behavioral-metadata-index (Cohere 1536-dim)
    - video-similarity-index (Cosmos 768-dim)
    """

    if not vectors_records:
        return {"vectors_stored": 0, "error": "No vectors to index"}

    try:
        logger.info(f"Processing {len(vectors_records)} vectors for multi-index storage")

        # ============================================================================
        # GROUP RECORDS BY TARGET INDEX
        # ============================================================================
        index_batches = {}

        for record in vectors_records:
            # Extract target index (default to legacy if not specified)
            target_index = record.pop("target_index", vector_index_name)

            if target_index not in index_batches:
                index_batches[target_index] = []

            index_batches[target_index].append(record)

        logger.info(f"Grouped records into {len(index_batches)} indices: {list(index_batches.keys())}")

        # ============================================================================
        # INDEX EACH GROUP SEPARATELY
        # ============================================================================
        batch_size = 100  # Recommended batch size for optimal performance
        total_vectors_stored = 0
        index_results = {}

        for index_name, index_records in index_batches.items():
            vectors_stored = 0

            logger.info(f"Indexing {len(index_records)} vectors in index: {index_name}")

            # Process in batches for each index
            for i in range(0, len(index_records), batch_size):
                batch = index_records[i:i + batch_size]

                response = s3vectors_client.put_vectors(
                    vectorBucketName=vector_bucket_name,
                    indexName=index_name,
                    vectors=batch
                )

                vectors_stored += len(batch)
                logger.info(f"Indexed batch of {len(batch)} vectors in {index_name} (total: {vectors_stored})")

            index_results[index_name] = {
                "vectors_stored": vectors_stored,
                "status": "success"
            }
            total_vectors_stored += vectors_stored

        logger.info(f"Successfully indexed all {total_vectors_stored} vectors across {len(index_batches)} indices")

        return {
            "vectors_stored": total_vectors_stored,
            "vector_bucket": vector_bucket_name,
            "indices_used": list(index_batches.keys()),
            "index_results": index_results,  # Per-index breakdown
            "total_batch_operations": sum((len(records) + batch_size - 1) // batch_size for records in index_batches.values()),
            "indexing_timestamp": datetime.utcnow().isoformat(),
            "multi_index_architecture": True
        }

    except Exception as e:
        logger.error(f"Failed to index vectors in S3 Vectors: {str(e)}")
        return {
            "vectors_stored": 0,
            "error": f"S3 Vectors indexing failed: {str(e)}"
        }


def prepare_embedding_inputs(behavioral_analysis: Dict[str, Any], scene_id: str) -> List[Dict[str, Any]]:
    """Prepare structured text inputs for embedding generation - FIXED for actual Phase 3 data structure"""

    embedding_inputs = []

    # SUCCESS: USE ACTUAL PHASE 3 STRUCTURE: behavioral_insights.scene_description
    behavioral_insights = behavioral_analysis.get('behavioral_insights', {})
    scene_description = behavioral_insights.get('scene_description', '')
    if scene_description and scene_description.strip():
        embedding_inputs.append({
            "type": "behavioral_insight",
            "id": "scene_description",
            "text": f"Behavioral insight for Tesla scene {scene_id}: {scene_description}"
        })

    # SUCCESS: USE ACTUAL PHASE 3 STRUCTURE: scene_understanding.comprehensive_analysis
    scene_understanding = behavioral_analysis.get('scene_understanding', {})
    comprehensive_analysis = scene_understanding.get('comprehensive_analysis', '')
    if comprehensive_analysis and comprehensive_analysis.strip():
        embedding_inputs.append({
            "type": "safety_assessment",
            "id": "comprehensive_analysis",
            "text": f"Scene understanding for Tesla scene {scene_id}: {comprehensive_analysis}"
        })

    # SUCCESS: EXTRACT analysis_quality as context
    analysis_quality = scene_understanding.get('analysis_quality', '')
    if analysis_quality and analysis_quality.strip():
        embedding_inputs.append({
            "type": "scene_context",
            "id": "analysis_quality",
            "text": f"Scene context for Tesla scene {scene_id} (analysis_quality): {analysis_quality}"
        })

    # SUCCESS: CREATE COMBINED ANALYSIS using actual content
    if scene_description or comprehensive_analysis:
        combined_text = f"Complete behavioral analysis for Tesla scene {scene_id}. "

        if scene_description:
            # Truncate very long descriptions to prevent token limits
            desc_preview = scene_description[:1500] + "..." if len(scene_description) > 1500 else scene_description
            combined_text += f"Scene description: {desc_preview} "

        if comprehensive_analysis:
            # Truncate very long analysis to prevent token limits
            analysis_preview = comprehensive_analysis[:1500] + "..." if len(comprehensive_analysis) > 1500 else comprehensive_analysis
            combined_text += f"Understanding: {analysis_preview}"

        embedding_inputs.append({
            "type": "combined_analysis",
            "id": "combined_summary",
            "text": combined_text
        })

    logger.info(f"Prepared {len(embedding_inputs)} text inputs for embedding generation")

    # DEBUG: Log what we're actually sending to Cohere
    for i, input_item in enumerate(embedding_inputs):
        text_length = len(input_item['text'])
        text_preview = input_item['text'][:200] + "..." if text_length > 200 else input_item['text']
        logger.info(f"  Input {i+1}: {input_item['type']} ({text_length} chars) - {text_preview}")

    return embedding_inputs


def calculate_behavioral_metrics(embeddings_vectors: List[Dict[str, Any]], behavioral_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate behavioral metrics from generated embeddings"""

    if not embeddings_vectors:
        return {"error": "No embeddings available for metrics calculation"}

    # Calculate vector statistics
    all_vectors = [emb["vector"] for emb in embeddings_vectors]
    vector_dimensions = len(all_vectors[0]) if all_vectors else 0

    # Simple behavioral scoring based on embedding patterns
    insight_count = len([emb for emb in embeddings_vectors if emb["input_type"] == "behavioral_insight"])
    safety_count = len([emb for emb in embeddings_vectors if emb["input_type"] == "safety_assessment"])
    recommendation_count = len([emb for emb in embeddings_vectors if emb["input_type"] == "recommendation"])

    # Behavioral complexity score (0.0 to 1.0)
    complexity_score = min(1.0, (insight_count + safety_count + recommendation_count) / 10.0)

    # Safety awareness score based on confidence scores from Claude analysis
    confidence_scores = behavioral_analysis.get('confidence_scores', {})
    safety_score = confidence_scores.get('overall', 0.5) if isinstance(confidence_scores, dict) else 0.5

    return {
        "behavioral_complexity_score": complexity_score,
        "safety_awareness_score": safety_score,
        "embedding_coverage": {
            "insights": insight_count,
            "safety_assessments": safety_count,
            "recommendations": recommendation_count
        },
        "vector_statistics": {
            "total_vectors": len(embeddings_vectors),
            "dimensions": vector_dimensions,
            "embedding_types": list(set(emb["input_type"] for emb in embeddings_vectors))
        }
    }


def extract_business_intelligence_metadata(behavioral_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract business intelligence metadata from Phase 3 behavioral analysis

    This function extracts structured categorical fields from the quantified_metrics
    that were generated by the enhanced Claude call in Phase 3.

    Args:
        behavioral_analysis: Complete Phase 3 behavioral analysis output

    Returns:
        Dictionary with business intelligence fields for S3 Vectors metadata
    """
    logger.info("Phase 4-5: Extracting business intelligence metadata from Phase 3 analysis")

    try:
        # Get quantified metrics which now includes business_intelligence from Claude call
        quantified_metrics = behavioral_analysis.get('quantified_metrics', {})
        business_intel = quantified_metrics.get('business_intelligence', {})

        # Extract structured categorical fields for S3 Vectors metadata
        metadata = {
            "environment_type": business_intel.get('environment_type', 'unknown'),
            "weather_condition": business_intel.get('weather_condition', 'unknown'),
            "scenario_type": business_intel.get('scenario_type', 'unknown'),
            "safety_criticality": business_intel.get('safety_criticality', 'unknown'),
            # Include quantified metrics that Phase 6 queries for filtering
            "risk_score": quantified_metrics.get('risk_score', 0.5),
            "safety_score": quantified_metrics.get('safety_score', 0.5),  # Phase 6 queries this
            "confidence_score": quantified_metrics.get('confidence_score', 0.5)
        }

        logger.info(f"Phase 4-5: Business intelligence extracted: {metadata}")
        return metadata

    except Exception as e:
        logger.error(f"Phase 4-5: Failed to extract business intelligence metadata: {str(e)}")
        # Return default values to prevent pipeline crashes
        return {
            "environment_type": "unknown",
            "weather_condition": "unknown",
            "scenario_type": "unknown",
            "safety_criticality": "unknown",
            "risk_score": 0.5,
            "safety_score": 0.5,  # Phase 6 queries this
            "confidence_score": 0.5
        }

def verify_s3_output_exists(bucket: str, key: str) -> None:
    """Verify output file was created in S3"""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        file_size = response.get('ContentLength', 0)
        if file_size == 0:
            raise RuntimeError(f"Output file exists but is empty: s3://{bucket}/{key}")
        logger.info(f"Verified output: s3://{bucket}/{key} ({file_size} bytes)")
    except s3_client.exceptions.NoSuchKey:
        raise RuntimeError(f"Output file not created: s3://{bucket}/{key}")


if __name__ == "__main__":
    main()