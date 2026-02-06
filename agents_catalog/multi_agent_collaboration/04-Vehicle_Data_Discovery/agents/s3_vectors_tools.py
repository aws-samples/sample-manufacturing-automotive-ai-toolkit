"""
Fleet Discovery Studio - S3 Vectors Tools (Cosmos + Cohere Multi-Index Architecture)
Enhanced for dual-index architecture with video and behavioral embeddings.

This module provides agents with access to fleet-wide statistical baselines using S3 Vectors
multi-index architecture, enabling quantitative anomaly detection and cross-modal similarity
analysis with Cosmos video embeddings and Cohere behavioral embeddings.
"""

import os
import json
import boto3
import logging
from typing import List, Dict, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)

# Helper functions for camera-specific ID processing (self-contained)
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

class S3VectorsClient:
    """
    Enhanced S3 Vectors client for multi-index Cosmos + Cohere architecture.
    Provides fleet-wide cross-modal pattern analysis for agents.

    Supported Indices:
    - video-similarity-index: Cosmos-Embed1 768-dim video embeddings
    - behavioral-metadata-index: Cohere embed-v4 1536-dim behavioral embeddings
    - behavioral-insights: Legacy Titan 1024-dim embeddings (backward compatibility)
    """

    def __init__(self):
        # Lazy initialization - create boto3 client only when needed
        self._client = None
        self.bucket = os.getenv('VECTOR_BUCKET_NAME', '')

        # Multi-Index Architecture Support
        self.video_index = os.getenv('VIDEO_INDEX_NAME', 'video-similarity-index')          # Cosmos 768-dim
        self.behavioral_index = os.getenv('BEHAVIORAL_INDEX_NAME', 'behavioral-metadata-index')  # Cohere 1536-dim
        self.legacy_index = os.getenv('LEGACY_INDEX_NAME', 'behavioral-insights')           # Titan 1024-dim (legacy)

        # Default index for backward compatibility
        self.index = self.behavioral_index  # Primary behavioral index

        logger.info(f"S3VectorsClient initialized with multi-index architecture:")
        logger.info(f"  Bucket: {self.bucket}")
        logger.info(f"  Video Index: {self.video_index} (Cosmos 768-dim)")
        logger.info(f"  Behavioral Index: {self.behavioral_index} (Cohere 1536-dim)")
        logger.info(f"  Legacy Index: {self.legacy_index} (Titan 1024-dim)")
        logger.info(f"  Default Index: {self.index}")

    @property
    def client(self):
        """Lazy boto3 client creation only when first accessed"""
        if self._client is None:
            logger.info("Creating boto3 s3vectors client on first use")
            self._client = boto3.client('s3vectors')
        return self._client

    async def query_fleet_statistics(self, scene_embeddings: List[float],
                                   scene_id: str,
                                   topK: int = 50) -> Dict[str, Any]:
        """
        Query fleet-wide statistical baselines for anomaly detection.
        Provides quantitative statistical context instead of qualitative reasoning.

        Args:
            scene_embeddings: Current scene's embedding vector
            scene_id: Current scene ID to exclude from results
            topK: Number of nearest neighbors for statistical baseline

        Returns:
            Statistical analysis including percentiles, means, and anomaly assessment
        """
        logger.info(f"Querying fleet statistics for {scene_id} with topK={topK}")

        try:
            if not scene_embeddings:
                logger.warning("No scene embeddings provided for fleet statistics")
                return self._get_fallback_statistics()

            # Query vector neighbors for statistical baseline
            query_vector = scene_embeddings[0] if isinstance(scene_embeddings[0], list) else scene_embeddings

            response = self.client.query_vectors(
                vectorBucketName=self.bucket,
                indexName=self.index,
                queryVector={"float32": query_vector},  # Correct AWS format
                topK=topK,
                returnMetadata=True,
                returnDistance=True
            )

            vectors = response.get('vectors', [])
            logger.info(f"Retrieved {len(vectors)} fleet scenes for statistical analysis")

            if not vectors:
                logger.warning("No fleet data available for statistical baseline")
                return self._get_fallback_statistics()

            # Extract metrics from fleet data for statistical analysis
            fleet_metrics = self._extract_fleet_metrics(vectors, scene_id)

            # Calculate statistical baselines
            statistics = self._calculate_statistical_baselines(fleet_metrics)

            # Assess current scene against fleet statistics
            statistics['anomaly_assessment'] = self._assess_scene_anomaly(
                scene_embeddings, vectors, scene_id
            )

            logger.info(f"Fleet statistics calculated from {len(fleet_metrics)} comparable scenes")
            return statistics

        except Exception as e:
            logger.error(f"Fleet statistics query failed: {str(e)}")
            return self._get_fallback_statistics(error=str(e))

    async def query_similar_behavioral_patterns(self, scene_embeddings: List[float],
                                              workflow_filters: Dict[str, Any],
                                              scene_id: str,
                                              max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Enhanced Phase 6: S3 Vectors Cross-Scene Intelligence
        Query S3 Vectors behavioral-insights index for similar scenes using embedding similarity.
        Provides cross-scene intelligence for iterative cycle enrichment.

        Args:
            scene_embeddings: List of embedding vectors from current scene
            workflow_filters: Filters from business objective (environment, risk thresholds, etc.)
            scene_id: Current scene ID to exclude from results
            max_results: Maximum number of similar scenes to return

        Returns:
            List of similar scene data with behavioral context for agent enrichment
        """
        logger.info(f"Querying S3 Vectors for similar scenes to {scene_id} with {len(scene_embeddings)} embeddings")

        if not scene_embeddings:
            logger.warning("No scene embeddings provided for similarity search")
            return []

        try:
            # Use the first embedding as the query vector (most representative)
            query_vector = scene_embeddings[0] if isinstance(scene_embeddings[0], list) else scene_embeddings

            # Build metadata filters based on workflow parameters using correct S3 Vectors filter format
            metadata_filters = {}

            # Apply environment type filters if specified (use $in operator)
            if workflow_filters.get('environment_types'):
                metadata_filters['environment_type'] = {"$in": workflow_filters['environment_types']}

            # Apply risk threshold filters if specified (use $gte operator)
            risk_threshold = workflow_filters.get('risk_threshold_min', 0.0)
            if risk_threshold > 0.0:
                metadata_filters['risk_score'] = {"$gte": risk_threshold}

            # Apply weather condition filters if specified (use $in operator)
            if workflow_filters.get('weather_conditions'):
                metadata_filters['weather_condition'] = {"$in": workflow_filters['weather_conditions']}

            logger.info(f"S3 Vectors query: topK={(max_results + 5) * 2}, filters={len(metadata_filters)} requested (will apply in Python)")
            # Query without metadata filters to avoid ValidationException on mixed schema
            # Apply filters in Python post-processing for compatibility
            logger.info("Using post-processing filter approach for mixed metadata compatibility")

            # Execute S3 Vectors similarity search without metadata filters (broader query)
            response = self.client.query_vectors(
                vectorBucketName=self.bucket,
                indexName=self.index,
                queryVector={"float32": query_vector},  # Correct format matching your storage pattern
                topK=(max_results + 5) * 2,  # Get more results since we'll filter in Python
                returnMetadata=True
                # Apply filters in Python instead of at query level for compatibility
            )

            # Parse S3 Vectors response (correct format for query_vectors API)
            search_results = response.get('vectors', [])

            logger.info(f"S3 Vectors returned {len(search_results)} initial results")

            # Apply metadata filters that were removed from S3 Vectors query
            filtered_results = []
            seen_scene_ids = set()  # Track seen scenes for deduplication
            for result in search_results:
                result_metadata = result.get('metadata', {})

                # Extract scene ID from camera-specific ID (handles both new and legacy formats)
                camera_id = result.get('id', '') or result_metadata.get('camera_id', '')
                if camera_id and "_CAM_" in camera_id:
                    result_scene_id = extract_scene_from_id(camera_id)
                else:
                    # Fallback to legacy scene_id field for backward compatibility
                    result_scene_id = result_metadata.get('scene_id', 'unknown')

                # Skip current scene and duplicate scenes (deduplication logic)
                if result_scene_id == scene_id or result_scene_id in seen_scene_ids:
                    continue

                seen_scene_ids.add(result_scene_id)

                # Apply business intelligence filters in Python (safe for mixed metadata)
                passes_filters = True

                # Environment type filter
                if metadata_filters.get('environment_type'):
                    env_filter = metadata_filters['environment_type']
                    if '$in' in env_filter:
                        if result_metadata.get('environment_type') not in env_filter['$in']:
                            passes_filters = False

                # Risk score filter
                if metadata_filters.get('risk_score') and passes_filters:
                    risk_filter = metadata_filters['risk_score']
                    if '$gte' in risk_filter:
                        result_risk = result_metadata.get('risk_score', 0.0)
                        if result_risk < risk_filter['$gte']:
                            passes_filters = False

                # Weather condition filter
                if metadata_filters.get('weather_condition') and passes_filters:
                    weather_filter = metadata_filters['weather_condition']
                    if '$in' in weather_filter:
                        if result_metadata.get('weather_condition') not in weather_filter['$in']:
                            passes_filters = False

                if passes_filters:
                    filtered_results.append(result)

            logger.info(f"After Python filtering: {len(filtered_results)} results remain (from {len(search_results)} initial)")

            # Process and enrich filtered results
            similar_scenes = []

            for result in filtered_results:
                result_metadata = result.get('metadata', {})
                result_scene_id = result_metadata.get('scene_id', 'unknown')
                similarity_score = result.get('score', 0.0)

                # Skip low similarity results
                if similarity_score < 0.7:
                    continue

                # Enrich with behavioral context
                enriched_scene = {
                    'scene_id': result_scene_id,
                    'similarity_score': similarity_score,
                    'behavioral_context': {
                        'environment_type': result_metadata.get('environment_type', 'unknown'),
                        'weather_condition': result_metadata.get('weather_condition', 'clear'),
                        'risk_score': result_metadata.get('risk_score', 0.0),
                        'safety_score': result_metadata.get('safety_score', 0.0),
                        'maneuver_types': result_metadata.get('maneuver_types', []),
                        'behavioral_insights': result_metadata.get('behavioral_insights', [])
                    },
                    'cross_scene_intelligence': {
                        'pattern_relevance': _calculate_pattern_relevance(result_metadata, workflow_filters),
                        'recommended_focus': _get_recommended_focus(result_metadata, workflow_filters),
                        'similarity_reason': _explain_similarity(result_metadata, workflow_filters)
                    }
                }

                similar_scenes.append(enriched_scene)

                # Stop when we have enough results
                if len(similar_scenes) >= max_results:
                    break

            logger.info(f"Found {len(similar_scenes)} similar scenes for cross-scene intelligence")

            # Sort by similarity score (highest first)
            similar_scenes.sort(key=lambda x: x['similarity_score'], reverse=True)

            return similar_scenes

        except Exception as e:
            logger.error(f"S3 Vectors query failed: {str(e)}")
            # Return empty list rather than failing the entire cycle
            logger.warning("Continuing without cross-scene intelligence due to S3 Vectors error")
            return []

    async def query_video_similarity(self, cosmos_embedding: List[float],
                                   scene_id: str,
                                   max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Query Cosmos video similarity index for visual pattern matching.
        Returns List[Dict] to match existing query_similar_behavioral_patterns pattern.

        Args:
            cosmos_embedding: 768-dim Cosmos-Embed1 video embedding
            scene_id: Current scene ID to exclude from results
            max_results: Maximum number of similar video scenes to return

        Returns:
            List of similar video scene dictionaries
        """
        logger.info(f"Querying Cosmos video similarity for {scene_id} with {len(cosmos_embedding) if cosmos_embedding else 0}-dim embedding")

        try:
            if not cosmos_embedding or len(cosmos_embedding) != 768:
                logger.warning(f"Invalid Cosmos embedding: expected 768-dim, got {len(cosmos_embedding) if cosmos_embedding else 0}")
                return []

            # Query video similarity index using Cosmos embeddings
            response = self.client.query_vectors(
                vectorBucketName=self.bucket,
                indexName=self.video_index,
                queryVector={"float32": cosmos_embedding},
                topK=max_results + 5,  # Get extra results for filtering
                returnMetadata=True,
                returnDistance=True
            )

            vectors = response.get('vectors', [])
            logger.info(f"Retrieved {len(vectors)} video similarity results from {self.video_index}")

            if not vectors:
                logger.warning("No video similarity data found")
                return []

            # Process video similarity results (matching behavioral patterns format)
            similar_scenes = []
            for vector in vectors:
                metadata = vector.get('metadata', {})
                result_scene_id = metadata.get('scene_id', 'unknown')

                # Skip current scene
                if result_scene_id == scene_id:
                    continue

                similarity_score = 1.0 - vector.get('distance', 1.0)  # Convert distance to similarity

                # Only include high-similarity results
                if similarity_score < 0.6:
                    continue

                # Create enriched scene data (matching behavioral patterns structure)
                enriched_scene = {
                    'scene_id': result_scene_id,
                    'similarity_score': round(similarity_score, 3),
                    'video_context': {
                        'camera_angles': metadata.get('camera_angles', []),
                        'scenario_type': metadata.get('scenario_type', 'unknown'),
                        'environmental_conditions': metadata.get('environmental_conditions', 'unknown'),
                        'temporal_patterns': metadata.get('temporal_patterns', []),
                        'processing_timestamp': metadata.get('processing_timestamp', '')
                    },
                    'cross_scene_intelligence': {
                        'pattern_relevance': self._calculate_video_pattern_relevance(metadata),
                        'recommended_focus': [f"Visual similarity analysis (score: {similarity_score:.2f})"],
                        'similarity_reason': f"Visual patterns match with {similarity_score:.2f} similarity using Cosmos embeddings"
                    }
                }

                similar_scenes.append(enriched_scene)

                if len(similar_scenes) >= max_results:
                    break

            # Sort by similarity score (matching existing pattern)
            similar_scenes.sort(key=lambda x: x['similarity_score'], reverse=True)
            logger.info(f"Found {len(similar_scenes)} similar video scenes using Cosmos embeddings")
            return similar_scenes

        except Exception as e:
            logger.error(f"Video similarity query failed: {str(e)}")
            logger.warning("Continuing without video similarity due to query error")
            return []

    async def query_cross_modal_similarity(self, scene_data: Dict[str, Any],
                                         scene_id: str,
                                         max_results: int = 5) -> Dict[str, Any]:
        """
        Query both video and behavioral indices for comprehensive cross-modal similarity.
        Handles List return types correctly.

        Args:
            scene_data: Dict containing cosmos_embedding and cohere_embedding
            scene_id: Current scene ID to exclude from results
            max_results: Maximum results per modality

        Returns:
            Dict with video patterns (List), behavioral patterns (List), and cross-modal insights
        """
        logger.info(f"Performing cross-modal similarity analysis for {scene_id}")

        results = {
            "video_patterns": [],      # List[Dict]
            "behavioral_patterns": [], # List[Dict]
            "cross_modal_insights": {},
            "similarity_summary": ""
        }

        try:
            # Extract embeddings from scene data
            cosmos_embedding = scene_data.get('cosmos_embedding', [])
            cohere_embedding = scene_data.get('cohere_embedding', [])

            # Query video similarity if Cosmos embedding available (returns List[Dict])
            if cosmos_embedding and len(cosmos_embedding) == 768:
                results["video_patterns"] = await self.query_video_similarity(
                    cosmos_embedding, scene_id, max_results
                )

            # Query behavioral similarity if Cohere embedding available (returns List[Dict])
            if cohere_embedding and len(cohere_embedding) == 1536:
                results["behavioral_patterns"] = await self.query_similar_behavioral_patterns(
                    cohere_embedding, {}, scene_id, max_results
                )

            # Generate cross-modal insights (both inputs are now List[Dict])
            results["cross_modal_insights"] = self._generate_cross_modal_insights(
                results["video_patterns"], results["behavioral_patterns"]
            )

            # Create summary
            video_count = len(results["video_patterns"])
            behavioral_count = len(results["behavioral_patterns"])
            results["similarity_summary"] = f"Cross-modal analysis: {video_count} video matches, {behavioral_count} behavioral matches"

            logger.info(f"Cross-modal analysis completed: {video_count} video + {behavioral_count} behavioral patterns")
            return results

        except Exception as e:
            logger.error(f"Cross-modal similarity failed: {str(e)}")
            results["error"] = str(e)
            return results

    def _calculate_video_pattern_relevance(self, metadata: Dict[str, Any]) -> float:
        """Calculate relevance score for video pattern matching"""
        relevance = 0.0

        # Camera angle diversity increases relevance
        camera_angles = metadata.get('camera_angles', [])
        if len(camera_angles) > 1:
            relevance += 0.3

        # Scenario type match increases relevance
        if metadata.get('scenario_type'):
            relevance += 0.4

        # Environmental conditions increase relevance
        if metadata.get('environmental_conditions'):
            relevance += 0.3

        return min(1.0, relevance)

    def _generate_cross_modal_insights(self, video_patterns: List[Dict],
                                     behavioral_patterns: List[Dict]) -> Dict[str, Any]:
        """
        Generate insights from cross-modal similarity analysis.
        Both inputs are List[Dict] now - fixed data type issue.
        """
        insights = {
            "pattern_correlation": "none",
            "recommendations": [],
            "cross_modal_confidence": 0.0
        }

        if not video_patterns and not behavioral_patterns:
            insights["pattern_correlation"] = "insufficient_data"
            return insights

        video_scenes = {p.get('scene_id') for p in video_patterns}
        behavioral_scenes = {p.get('scene_id') for p in behavioral_patterns}

        overlap = video_scenes.intersection(behavioral_scenes)
        total_unique = len(video_scenes.union(behavioral_scenes))
        overlap_ratio = len(overlap) / max(total_unique, 1)

        if overlap_ratio > 0.5:
            insights["pattern_correlation"] = "high"
            insights["cross_modal_confidence"] = round(overlap_ratio, 3)
            insights["recommendations"].append("Strong video-behavioral correlation detected")
        elif overlap_ratio > 0.2:
            insights["pattern_correlation"] = "moderate"
            insights["cross_modal_confidence"] = round(overlap_ratio, 3)
            insights["recommendations"].append("Moderate cross-modal pattern alignment")
        else:
            insights["pattern_correlation"] = "low"
            insights["cross_modal_confidence"] = round(overlap_ratio, 3)
            insights["recommendations"].append("Distinct video vs behavioral similarity patterns")

        return insights

    def detect_statistical_anomaly(self, scene_embedding: List[float],
                                 threshold: float = 0.75) -> Dict[str, Any]:
        """
        Calculates anomaly score based on vector isolation (distance to nearest neighbors).
        Uses statistical distance analysis instead of qualitative reasoning.

        Args:
            scene_embedding: Current scene's embedding vector
            threshold: Similarity threshold for anomaly detection

        Returns:
            Dict with anomaly status, score (0.0-1.0), and statistical reasoning
        """
        try:
            # 1. Query for neighbors (k-NN search)
            response = self.client.query_vectors(
                vectorBucketName=self.bucket,
                indexName=self.index,
                queryVector={'float32': scene_embedding},  # AWS docs require VectorData object format
                topK=5,  # Check top 5 neighbors
                returnDistance=True,  # Include distance for anomaly scoring
                returnMetadata=False  # Don't need metadata for anomaly detection
            )

            vectors = response.get('vectors', [])  # AWS API returns 'vectors', not 'hits'

            # Cold Start Handling: If DB is empty, everything is an anomaly
            if not vectors:
                return {
                    "is_anomaly": True,
                    "anomaly_score": 1.0,
                    "anomaly_severity": 1.0,
                    "reason": "Cold start - No similar scenes found in database",
                    "statistical_context": "No fleet baseline available"
                }

            # 2. Calculate 'Weirdness' based on distance (AWS API returns distance, not similarity)
            # S3 Vectors returns distance (0.0 = identical, higher = more different)
            distances = [vector.get('distance', 1.0) for vector in vectors]
            closest_distance = min(distances)  # Lowest distance = closest match

            # Convert distance to similarity for threshold comparison
            # For cosine distance: similarity = 1 - distance
            closest_match_similarity = 1.0 - closest_distance

            # Anomaly Score: How far is the *closest* neighbor?
            anomaly_score = closest_distance  # Distance directly represents anomaly

            # 3. The Verdict
            is_anomaly = closest_match_similarity < threshold

            return {
                "is_anomaly": is_anomaly,
                "anomaly_score": round(anomaly_score, 3),
                "anomaly_severity": round(anomaly_score, 3),  # For agent compatibility
                "closest_match_similarity": round(closest_match_similarity, 3),
                "closest_distance": round(closest_distance, 3),
                "reason": f"Statistical analysis: Closest neighbor has {closest_match_similarity:.2f} similarity (Fleet threshold: {threshold})",
                "statistical_context": f"Compared against {len(vectors)} fleet scenes"
            }

        except Exception as e:
            logger.warning(f"Statistical anomaly detection failed (failing open): {e}")
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "anomaly_severity": 0.0,
                "reason": f"Statistical analysis error: {e}",
                "statistical_context": "Unable to query fleet baselines"
            }

    def _extract_fleet_metrics(self, vectors: List[Dict], exclude_scene_id: str) -> List[Dict[str, Any]]:
        """Extract behavioral metrics from fleet scenes for statistical analysis"""
        fleet_metrics = []

        for vector in vectors:
            metadata = vector.get('metadata', {})
            scene_id = metadata.get('scene_id', '')

            # Skip current scene
            if scene_id == exclude_scene_id:
                continue

            # Extract relevant metrics
            metrics = {
                'scene_id': scene_id,
                'risk_score': metadata.get('risk_score', 0.0),
                'safety_score': metadata.get('safety_score', 0.0),
                'similarity_distance': vector.get('distance', 1.0),
                'environment_type': metadata.get('environment_type', 'unknown'),
                'weather_condition': metadata.get('weather_condition', 'clear')
            }

            fleet_metrics.append(metrics)

        return fleet_metrics

    def _calculate_statistical_baselines(self, fleet_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistical baselines from fleet data"""
        if not fleet_metrics:
            return self._get_fallback_statistics()

        # Extract numeric metrics
        risk_scores = [m['risk_score'] for m in fleet_metrics if m['risk_score'] is not None]
        safety_scores = [m['safety_score'] for m in fleet_metrics if m['safety_score'] is not None]
        distances = [m['similarity_distance'] for m in fleet_metrics]

        # Calculate percentiles and statistics
        statistics = {
            'fleet_size': len(fleet_metrics),
            'risk_score_statistics': self._calculate_percentiles(risk_scores) if risk_scores else {},
            'safety_score_statistics': self._calculate_percentiles(safety_scores) if safety_scores else {},
            'similarity_statistics': self._calculate_percentiles(distances) if distances else {},
            'environment_distribution': self._calculate_distribution([m['environment_type'] for m in fleet_metrics]),
            'weather_distribution': self._calculate_distribution([m['weather_condition'] for m in fleet_metrics])
        }

        return statistics

    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate statistical percentiles for a list of values"""
        if not values:
            return {}

        sorted_values = sorted(values)
        n = len(sorted_values)

        return {
            'mean': sum(values) / n,
            'min': min(values),
            'max': max(values),
            'p25': sorted_values[int(n * 0.25)] if n > 0 else 0,
            'p50': sorted_values[int(n * 0.50)] if n > 0 else 0,
            'p75': sorted_values[int(n * 0.75)] if n > 0 else 0,
            'p90': sorted_values[int(n * 0.90)] if n > 0 else 0,
            'p95': sorted_values[int(n * 0.95)] if n > 0 else 0
        }

    def _calculate_distribution(self, values: List[str]) -> Dict[str, int]:
        """Calculate distribution counts for categorical values"""
        distribution = {}
        for value in values:
            distribution[value] = distribution.get(value, 0) + 1
        return distribution

    def _assess_scene_anomaly(self, scene_embeddings: List[float],
                            fleet_vectors: List[Dict], scene_id: str) -> Dict[str, Any]:
        """Assess current scene anomaly status against fleet statistics"""
        if not fleet_vectors:
            return {
                'is_statistical_anomaly': True,
                'anomaly_percentile': 100.0,
                'fleet_context': 'No fleet data available'
            }

        # Calculate similarity distances to all fleet scenes
        distances = []
        for vector in fleet_vectors:
            if vector.get('metadata', {}).get('scene_id', '') != scene_id:
                distances.append(vector.get('distance', 1.0))

        if not distances:
            return {
                'is_statistical_anomaly': True,
                'anomaly_percentile': 100.0,
                'fleet_context': 'No comparable fleet scenes'
            }

        # Find closest distance (most similar scene)
        closest_distance = min(distances)

        # Calculate percentile rank
        worse_count = sum(1 for d in distances if d > closest_distance)
        percentile = (worse_count / len(distances)) * 100

        # Anomaly threshold: if in top 10% of distances (most isolated)
        is_anomaly = percentile >= 90.0

        return {
            'is_statistical_anomaly': is_anomaly,
            'anomaly_percentile': round(percentile, 1),
            'closest_fleet_distance': round(closest_distance, 3),
            'fleet_context': f'Compared against {len(distances)} fleet scenes'
        }

    def _get_fallback_statistics(self, error: str = None) -> Dict[str, Any]:
        """Return fallback statistics when fleet data unavailable"""
        return {
            'fleet_size': 0,
            'error': error,
            'risk_score_statistics': {},
            'safety_score_statistics': {},
            'similarity_statistics': {},
            'environment_distribution': {},
            'weather_distribution': {},
            'anomaly_assessment': {
                'is_statistical_anomaly': False,
                'anomaly_percentile': 0.0,
                'fleet_context': 'No fleet data available'
            }
        }


# Helper functions for similarity analysis
def _calculate_pattern_relevance(scene_metadata: Dict[str, Any], workflow_filters: Dict[str, Any]) -> float:
    """
    Calculate how relevant a similar scene is based on workflow parameters.
    """
    relevance_score = 0.0
    total_factors = 0

    # Environment type relevance
    if workflow_filters.get('environment_types') and scene_metadata.get('environment_type'):
        total_factors += 1
        if scene_metadata['environment_type'] in workflow_filters['environment_types']:
            relevance_score += 1.0

    # Risk threshold relevance
    if workflow_filters.get('risk_threshold_min') and scene_metadata.get('risk_score'):
        total_factors += 1
        scene_risk = scene_metadata['risk_score']
        threshold_risk = workflow_filters['risk_threshold_min']

        # Higher relevance if scene risk is close to threshold
        if scene_risk >= threshold_risk:
            relevance_score += min(1.0, scene_risk / (threshold_risk + 0.1))

    # Weather condition relevance
    if workflow_filters.get('weather_conditions') and scene_metadata.get('weather_condition'):
        total_factors += 1
        if scene_metadata['weather_condition'] in workflow_filters['weather_conditions']:
            relevance_score += 1.0

    # Maneuver type relevance
    if workflow_filters.get('maneuver_types') and scene_metadata.get('maneuver_types'):
        total_factors += 1
        scene_maneuvers = set(scene_metadata['maneuver_types'])
        filter_maneuvers = set(workflow_filters['maneuver_types'])

        overlap = len(scene_maneuvers.intersection(filter_maneuvers))
        if len(filter_maneuvers) > 0:
            relevance_score += overlap / len(filter_maneuvers)

    return relevance_score / total_factors if total_factors > 0 else 0.0


def _get_recommended_focus(scene_metadata: Dict[str, Any], workflow_filters: Dict[str, Any]) -> List[str]:
    """
    Generate recommended focus areas based on similar scene characteristics.
    """
    focus_areas = []

    # Risk-based focus
    risk_score = scene_metadata.get('risk_score', 0.0)
    if risk_score > 0.5:
        focus_areas.append(f"High-risk pattern analysis (risk: {risk_score:.2f})")

    # Environment-based focus
    environment = scene_metadata.get('environment_type', '')
    if environment and environment in workflow_filters.get('environment_types', []):
        focus_areas.append(f"{environment.title()} environment behavior patterns")

    # Safety-based focus
    safety_score = scene_metadata.get('safety_score', 0.0)
    if safety_score < 0.8:
        focus_areas.append(f"Safety improvement opportunities (current: {safety_score:.2f})")

    # Maneuver-based focus
    maneuvers = scene_metadata.get('maneuver_types', [])
    relevant_maneuvers = [m for m in maneuvers if m in workflow_filters.get('maneuver_types', [])]
    if relevant_maneuvers:
        focus_areas.append(f"Maneuver analysis: {', '.join(relevant_maneuvers)}")

    return focus_areas[:3]  # Limit to top 3 focus areas


def _explain_similarity(scene_metadata: Dict[str, Any], workflow_filters: Dict[str, Any]) -> str:
    """
    Generate human-readable explanation of why this scene is similar.
    """
    similarity_reasons = []

    # Environment similarity
    environment = scene_metadata.get('environment_type', '')
    if environment and environment in workflow_filters.get('environment_types', []):
        similarity_reasons.append(f"same {environment} environment")

    # Risk similarity
    risk_score = scene_metadata.get('risk_score', 0.0)
    threshold = workflow_filters.get('risk_threshold_min', 0.0)
    if risk_score >= threshold and threshold > 0:
        similarity_reasons.append(f"similar risk profile ({risk_score:.2f})")

    # Weather similarity
    weather = scene_metadata.get('weather_condition', '')
    if weather and weather in workflow_filters.get('weather_conditions', []):
        similarity_reasons.append(f"{weather} weather conditions")

    # Maneuver similarity
    maneuvers = scene_metadata.get('maneuver_types', [])
    relevant_maneuvers = [m for m in maneuvers if m in workflow_filters.get('maneuver_types', [])]
    if relevant_maneuvers:
        similarity_reasons.append(f"similar maneuvers ({', '.join(relevant_maneuvers)})")

    if similarity_reasons:
        return f"Similar due to: {', '.join(similarity_reasons)}"
    else:
        return "Similar behavioral embedding patterns"


# Global client instance for agents to use (lazy initialization)
s3_vectors_client = None


def _get_s3_vectors_client():
    """Get S3 Vectors client with lazy initialization to avoid AgentCore timeout"""
    global s3_vectors_client
    if s3_vectors_client is None:
        s3_vectors_client = S3VectorsClient()
    return s3_vectors_client


# Tool functions for AgentCore integration
def query_fleet_statistics_tool(scene_embeddings: List[float], scene_id: str) -> str:
    """
    Tool wrapper for fleet statistics query - returns JSON string for agent consumption
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        client = _get_s3_vectors_client()
        result = loop.run_until_complete(
            client.query_fleet_statistics(scene_embeddings, scene_id)
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Fleet statistics tool error: {e}")
        return json.dumps({"error": str(e), "fleet_size": 0})
    finally:
        loop.close()


def query_similar_behavioral_patterns_tool(scene_embeddings: List[float],
                                         scene_id: str,
                                         workflow_filters: Dict[str, Any] = None,
                                         max_results: int = 10) -> str:
    """
    Tool wrapper for similar behavioral patterns query - returns JSON string for agent consumption
    """
    import asyncio

    if workflow_filters is None:
        workflow_filters = {}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        client = _get_s3_vectors_client()
        result = loop.run_until_complete(
            client.query_similar_behavioral_patterns(
                scene_embeddings, workflow_filters, scene_id, max_results
            )
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Similar patterns tool error: {e}")
        return json.dumps({"error": str(e), "similar_scenes": []})
    finally:
        loop.close()


def detect_statistical_anomaly_tool(scene_embedding: List[float]) -> str:
    """
    Tool wrapper for statistical anomaly detection - returns JSON string for agent consumption
    """
    try:
        client = _get_s3_vectors_client()
        result = client.detect_statistical_anomaly(scene_embedding)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Statistical anomaly tool error: {e}")
        return json.dumps({
            "error": str(e),
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "anomaly_severity": 0.0
        })


# NEW: Enhanced Multi-Index Architecture Tool Functions

def query_video_similarity_tool(cosmos_embedding: List[float], scene_id: str, max_results: int = 10) -> str:
    """
    Tool wrapper for Cosmos video similarity query - returns JSON string for agent consumption.
    Uses the new video-similarity-index with 768-dim Cosmos embeddings.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        client = _get_s3_vectors_client()  # SUCCESS: Uses existing helper
        result = loop.run_until_complete(
            client.query_video_similarity(cosmos_embedding, scene_id, max_results)  # SUCCESS: Uses video similarity method
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Video similarity tool error: {e}")
        return json.dumps({"error": str(e), "similar_video_scenes": []})
    finally:
        loop.close()


def query_cross_modal_similarity_tool(scene_data: Dict[str, Any], scene_id: str, max_results: int = 5) -> str:
    """
    Tool wrapper for cross-modal similarity analysis - returns JSON string for agent consumption.
    Combines Cosmos video similarity + Cohere behavioral similarity.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        client = _get_s3_vectors_client()  # SUCCESS: Uses existing helper
        result = loop.run_until_complete(
            client.query_cross_modal_similarity(scene_data, scene_id, max_results)  # SUCCESS: Uses cross-modal similarity method
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Cross-modal similarity tool error: {e}")
        return json.dumps({
            "error": str(e),
            "video_patterns": [],
            "behavioral_patterns": [],
            "cross_modal_insights": {}
        })
    finally:
        loop.close()