#!/usr/bin/env python3
import boto3
import json
import logging
import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Configure logging (following dashboard_api.py pattern)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS Configuration from environment variables
FLEET_BUCKET = os.getenv("S3_BUCKET", "")
VECTOR_BUCKET = os.getenv("VECTOR_BUCKET_NAME", "")

@dataclass
class SceneEmbeddings:
    """Data structure for scene embedding data"""
    scene_id: str
    cohere_embedding: np.ndarray  # 1536-dim behavioral embedding
    cosmos_embedding: np.ndarray  # 768-dim visual embedding
    risk_score: float
    description: str
    metadata: Dict
    timestamp: str

class EmbeddingRetrievalService:
    """
    Service for retrieving embeddings from S3 phase4-5 JSON outputs
    Following patterns from dashboard_api.py for S3 operations and error handling
    """

    def __init__(self, s3_client=None):
        """Initialize with optional S3 client (allows dependency injection)"""
        self.s3_client = s3_client or boto3.client('s3')
        self.fleet_bucket = FLEET_BUCKET

    def get_current_scene_count(self) -> int:
        """
        Dynamically get current number of processed scenes
        Never hardcode scene count - always scan current dataset
        """
        try:
            logger.info("Scanning S3 bucket for current scene count...")

            response = self.s3_client.list_objects_v2(
                Bucket=self.fleet_bucket,
                Prefix="processed/phase4-5/",
                Delimiter="/"
            )

            # Count scene directories (each CommonPrefix is a scene directory)
            scene_count = len(response.get('CommonPrefixes', []))

            logger.info(f"Current dataset contains {scene_count} scenes (dynamic count)")
            return scene_count

        except Exception as e:
            logger.error(f"Failed to get current scene count: {str(e)}")
            return 0

    def list_available_scenes(self) -> List[str]:
        """
        Get list of all scene IDs that have phase4-5 embeddings available
        Returns scene IDs in format: ['scene_0001', 'scene_0002', ...]
        """
        try:
            logger.info("Listing available scenes with phase4-5 embeddings...")

            response = self.s3_client.list_objects_v2(
                Bucket=self.fleet_bucket,
                Prefix="processed/phase4-5/",
                Delimiter="/"
            )

            scene_ids = []
            for prefix_info in response.get('CommonPrefixes', []):
                # Extract scene ID from prefix like "processed/phase4-5/scene_0123/"
                prefix = prefix_info['Prefix']
                scene_id = prefix.rstrip('/').split('/')[-1]
                scene_ids.append(scene_id)

            logger.info(f"Found {len(scene_ids)} scenes with embeddings available")
            return sorted(scene_ids)

        except Exception as e:
            logger.error(f"Failed to list available scenes: {str(e)}")
            return []

    def load_scene_embeddings(self, scene_id: str) -> Optional[SceneEmbeddings]:
        """
        Load embeddings and metadata for a single scene from S3
        Following dashboard_api.py pattern for S3 operations and JSON parsing
        """
        try:
            # S3 key pattern established in CDK: processed/phase4-5/{scene_id}/embeddings_output.json
            s3_key = f"processed/phase4-5/{scene_id}/embeddings_output.json"

            logger.debug(f"Loading embeddings for {scene_id} from {s3_key}")

            # Get S3 object (following dashboard_api.py pattern)
            obj = self.s3_client.get_object(Bucket=self.fleet_bucket, Key=s3_key)
            data = json.loads(obj['Body'].read())

            # FIXED: Extract embeddings from actual multi_model_embeddings structure
            multi_model_data = data.get('multi_model_embeddings', {})

            # Get behavioral embedding (Cohere - 1536 dim)
            cohere_vector = None
            cohere_data = multi_model_data.get('cohere', {})
            if 'embeddings' in cohere_data and cohere_data['embeddings']:
                # Cohere embeddings is a list of embedding objects
                cohere_embeddings_list = cohere_data['embeddings']
                if cohere_embeddings_list and len(cohere_embeddings_list) > 0:
                    # Use first embedding object and extract its vector
                    first_embedding = cohere_embeddings_list[0]
                    if 'vector' in first_embedding:
                        cohere_vector = np.array(first_embedding['vector'], dtype=np.float32)

            # Get visual embedding (Cosmos - 768 dim)
            cosmos_vector = None
            cosmos_data = multi_model_data.get('cosmos', {})
            if 'embeddings' in cosmos_data and cosmos_data['embeddings']:
                # Cosmos embeddings is a list of camera-specific S3 records
                cosmos_embeddings_list = cosmos_data['embeddings']
                if cosmos_embeddings_list and len(cosmos_embeddings_list) > 0:
                    # Try to find CAM_FRONT first, otherwise use any available
                    front_embedding = None
                    any_embedding = None

                    for embedding_record in cosmos_embeddings_list:
                        if 'metadata' in embedding_record and embedding_record['metadata'].get('camera_name') == 'CAM_FRONT':
                            front_embedding = embedding_record
                            break
                        if any_embedding is None:
                            any_embedding = embedding_record

                    # Use front camera if available, otherwise any camera
                    selected_embedding = front_embedding or any_embedding
                    if selected_embedding and 'data' in selected_embedding and 'float32' in selected_embedding['data']:
                        cosmos_vector = np.array(selected_embedding['data']['float32'], dtype=np.float32)

            # Extract risk score and metadata
            risk_score = 0.5  # Default
            description = f"Scene {scene_id}"

            # Try to get risk score from various possible locations in the data
            if 'behavioral_analysis' in data:
                behavioral_data = data['behavioral_analysis']
                if isinstance(behavioral_data, dict):
                    risk_score = behavioral_data.get('risk_score', risk_score)
                    description = behavioral_data.get('description', description) or behavioral_data.get('summary', description)

            # Skip scene if we don't have both embeddings
            if cohere_vector is None or cosmos_vector is None:
                logger.warning(f"Scene {scene_id} missing embeddings - cohere: {cohere_vector is not None}, cosmos: {cosmos_vector is not None}")
                return None

            # Validate embedding dimensions
            if len(cohere_vector) != 1536:
                logger.warning(f"Scene {scene_id} has invalid Cohere embedding dimension: {len(cohere_vector)} (expected 1536)")
                return None
            if len(cosmos_vector) != 768:
                logger.warning(f"Scene {scene_id} has invalid Cosmos embedding dimension: {len(cosmos_vector)} (expected 768)")
                return None

            return SceneEmbeddings(
                scene_id=scene_id,
                cohere_embedding=cohere_vector,
                cosmos_embedding=cosmos_vector,
                risk_score=risk_score,
                description=description,
                metadata=data.get('metadata', {}),
                timestamp=datetime.utcnow().isoformat()
            )

        except Exception as e:
            logger.error(f"Failed to load embeddings for scene {scene_id}: {str(e)}")
            return None

    def load_all_scene_embeddings(self, progress_callback=None) -> List[SceneEmbeddings]:
        """
        Load embeddings for all available scenes
        Returns list of SceneEmbeddings objects for clustering
        """
        try:
            logger.info("Loading embeddings for all available scenes...")

            # Get current scene list dynamically
            scene_ids = self.list_available_scenes()
            current_count = len(scene_ids)

            if current_count == 0:
                logger.warning("No scenes with embeddings found")
                return []

            logger.info(f"Loading embeddings for {current_count} scenes (dynamic count)")

            embeddings_list = []
            loaded_count = 0
            failed_count = 0

            for scene_id in scene_ids:
                scene_embeddings = self.load_scene_embeddings(scene_id)
                if scene_embeddings:
                    embeddings_list.append(scene_embeddings)
                    loaded_count += 1
                else:
                    failed_count += 1

                # Progress logging for large datasets
                if (loaded_count + failed_count) % 100 == 0:
                    logger.info(f"Processed {loaded_count + failed_count}/{current_count} scenes...")

                    # Apple-grade progress callback integration
                    if progress_callback:
                        progress_callback(loaded_count + failed_count, current_count, f"scene {scene_id}")

                # Real-time progress updates for Apple-grade UX (every 10 scenes)
                elif progress_callback and (loaded_count + failed_count) % 10 == 0:
                    progress_callback(loaded_count + failed_count, current_count, f"scene {scene_id}")

            logger.info(f"Embedding loading complete: {loaded_count} successful, {failed_count} failed")

            if loaded_count == 0:
                logger.error("No valid embeddings loaded - cannot perform clustering")
                return []

            return embeddings_list

        except Exception as e:
            logger.error(f"Failed to load all scene embeddings: {str(e)}")
            return []

    def get_embeddings_summary(self) -> Dict:
        """
        Get summary statistics about available embeddings
        Useful for health checks and debugging
        """
        try:
            scene_count = self.get_current_scene_count()
            scene_ids = self.list_available_scenes()

            return {
                "total_scenes_in_bucket": scene_count,
                "scenes_with_embeddings": len(scene_ids),
                "coverage_ratio": len(scene_ids) / scene_count if scene_count > 0 else 0.0,
                "sample_scene_ids": scene_ids[:5] if scene_ids else [],
                "bucket": self.fleet_bucket,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get embeddings summary: {str(e)}")
            return {"error": str(e)}

# Convenience functions for direct usage
def get_current_dataset_size() -> int:
    """Get current number of scenes with embeddings (never hardcoded)"""
    service = EmbeddingRetrievalService()
    return service.get_current_scene_count()

def load_all_embeddings(progress_callback=None) -> List[SceneEmbeddings]:
    """Load all available scene embeddings for clustering"""
    service = EmbeddingRetrievalService()
    return service.load_all_scene_embeddings(progress_callback=progress_callback)