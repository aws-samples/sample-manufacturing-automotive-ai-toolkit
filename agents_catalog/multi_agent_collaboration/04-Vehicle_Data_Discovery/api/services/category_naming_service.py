#!/usr/bin/env python3
import boto3
import json
import logging
from typing import List, Optional
from datetime import datetime

# Configure logging (following dashboard_api.py pattern)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import cluster data structures
from .odd_discovery_service import DiscoveredCluster
from .embedding_retrieval import SceneEmbeddings

class CategoryNamingService:
    """
    Intelligent cluster naming service using Claude via AWS Bedrock
    Handles cold start problem with fallbacks for small clusters
    Following patterns from dashboard_api.py for AWS operations and error handling
    """

    def __init__(self, bedrock_client=None):
        """Initialize with optional Bedrock client (allows dependency injection)"""
        try:
            from dependencies import AWS_REGION
            self.bedrock_client = bedrock_client or boto3.client('bedrock-runtime', region_name=AWS_REGION)
            self.bedrock_available = True
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            self.bedrock_available = False

    def get_closest_to_centroid(self, cluster_scenes: List[SceneEmbeddings],
                              centroid: any, num_scenes: int = 5) -> List[SceneEmbeddings]:
        """
        Get scenes closest to cluster centroid for naming analysis
        Uses behavioral embeddings for similarity calculation
        """
        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            if len(cluster_scenes) <= num_scenes:
                return cluster_scenes  # Return all if we have few scenes

            # Calculate similarities to centroid
            scene_vectors = np.array([scene.cohere_embedding for scene in cluster_scenes])

            # ENHANCED: Robust centroid handling for JSON serialization and various array types
            try:
                if isinstance(centroid, list):
                    # Convert from JSON-serialized list to numpy array
                    centroid_vector = np.array(centroid, dtype=np.float32)
                elif hasattr(centroid, 'tolist'):
                    # Already a numpy array
                    centroid_vector = centroid.astype(np.float32)
                else:
                    # Try to convert whatever it is to numpy array
                    centroid_vector = np.array(centroid, dtype=np.float32)

                # Ensure correct shape for cosine similarity (must be 2D)
                if centroid_vector.ndim == 1:
                    centroid_vector = centroid_vector.reshape(1, -1)
                elif centroid_vector.ndim > 2:
                    # Flatten multi-dimensional arrays to 1D, then reshape to 2D
                    centroid_vector = centroid_vector.flatten().reshape(1, -1)

                # Validate embedding dimensions (should be 1536 for Cohere)
                if centroid_vector.shape[1] != 1536:
                    logger.warning(f"Unexpected centroid dimensions: {centroid_vector.shape}, expected (1, 1536)")

            except Exception as reshape_error:
                logger.error(f"Failed to reshape centroid: {reshape_error}")
                logger.error(f"Centroid type: {type(centroid)}, shape: {getattr(centroid, 'shape', 'no shape')}")
                raise ValueError(f"Cannot process centroid for similarity calculation: {reshape_error}")

            similarities = cosine_similarity(scene_vectors, centroid_vector).flatten()

            # Get indices of most similar scenes
            top_indices = np.argsort(similarities)[-num_scenes:]

            return [cluster_scenes[i] for i in top_indices]

        except Exception as e:
            logger.error(f"Failed to get centroid scenes: {str(e)}")
            # Fallback: return first N scenes
            return cluster_scenes[:num_scenes]

    def get_most_representative_scene(self, cluster: DiscoveredCluster) -> Optional[SceneEmbeddings]:
        """
        Find the scene most similar to the cluster centroid (for Find Similar functionality).
        Handles JSON serialization issues where centroid might be list vs numpy array.
        """
        try:
            if not cluster.scenes:
                logger.warning("No scenes in cluster for representative selection")
                return None

            if len(cluster.scenes) == 1:
                return cluster.scenes[0]  # Only one option

            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            # Handle centroid with same robust logic as get_closest_to_centroid
            try:
                centroid = cluster.centroid_behavioral

                if isinstance(centroid, list):
                    # Convert from JSON-serialized list to numpy array
                    centroid_vector = np.array(centroid, dtype=np.float32)
                elif hasattr(centroid, 'tolist'):
                    # Already a numpy array
                    centroid_vector = centroid.astype(np.float32)
                else:
                    # Try to convert whatever it is to numpy array
                    centroid_vector = np.array(centroid, dtype=np.float32)

                # Ensure correct shape for cosine similarity (must be 2D)
                if centroid_vector.ndim == 1:
                    centroid_vector = centroid_vector.reshape(1, -1)
                elif centroid_vector.ndim > 2:
                    # Flatten multi-dimensional arrays to 1D, then reshape to 2D
                    centroid_vector = centroid_vector.flatten().reshape(1, -1)

                # Validate embedding dimensions (should be 1536 for Cohere)
                if centroid_vector.shape[1] != 1536:
                    logger.warning(f"Unexpected centroid dimensions: {centroid_vector.shape}, expected (1, 1536)")

            except Exception as centroid_error:
                logger.error(f"Failed to process centroid: {centroid_error}")
                return cluster.scenes[0]  # Fallback to first scene

            # Calculate similarities for all scenes in cluster
            scene_similarities = []
            for scene in cluster.scenes:
                try:
                    # Ensure scene embedding is also numpy array
                    if hasattr(scene.cohere_embedding, 'tolist'):
                        scene_embedding = scene.cohere_embedding
                    elif isinstance(scene.cohere_embedding, list):
                        scene_embedding = np.array(scene.cohere_embedding, dtype=np.float32)
                    else:
                        scene_embedding = np.array(scene.cohere_embedding, dtype=np.float32)

                    # Reshape for sklearn if needed
                    scene_2d = scene_embedding.reshape(1, -1) if scene_embedding.ndim == 1 else scene_embedding

                    # Calculate cosine similarity
                    similarity = cosine_similarity(centroid_vector, scene_2d)[0][0]
                    scene_similarities.append((similarity, scene))

                except Exception as scene_error:
                    logger.warning(f"Error calculating similarity for scene {scene.scene_id}: {scene_error}")
                    # Assign low similarity so it's not chosen as representative
                    scene_similarities.append((0.0, scene))

            # Find scene with highest similarity to centroid
            if scene_similarities:
                # Sort by similarity (highest first)
                scene_similarities.sort(key=lambda x: x[0], reverse=True)
                best_similarity, representative_scene = scene_similarities[0]

                logger.info(f"Representative scene for cluster {cluster.cluster_id}: {representative_scene.scene_id} (similarity: {best_similarity:.3f})")
                return representative_scene

            # Fallback if no similarities calculated
            return cluster.scenes[0]

        except Exception as e:
            logger.error(f"Failed to find representative scene for cluster {cluster.cluster_id}: {e}")
            # Fallback: return first scene in cluster
            return cluster.scenes[0] if cluster.scenes else None

    def generate_category_name(self, cluster: DiscoveredCluster) -> str:
        """
        Generate intelligent category name for discovered cluster
        Handles cold start problem with fallbacks for small clusters
        """
        try:
            if not self.bedrock_available:
                logger.warning("Bedrock not available - using fallback naming")
                return self.generate_fallback_name(cluster)

            logger.info(f"Generating category name for cluster {cluster.cluster_id} ({cluster.scene_count} scenes)")

            # FIXED: Cold start safety check
            if cluster.scene_count < 5:
                logger.info(f"Small cluster detected: {cluster.scene_count} scenes. Using all scenes for naming.")
                centroid_scenes = cluster.scenes  # Send ALL available scenes
                naming_strategy = "full_cluster"
            else:
                centroid_scenes = self.get_closest_to_centroid(
                    cluster.scenes,
                    cluster.centroid_behavioral,
                    5
                )  # Standard approach
                naming_strategy = "centroid_subset"

            # Prepare scene descriptions for Claude
            scene_descriptions = []
            for scene in centroid_scenes:
                # Use scene description or create basic one from metadata
                desc = scene.description
                if not desc or desc == f"Scene {scene.scene_id}":
                    # Generate basic description from available metadata
                    risk_level = "high" if scene.risk_score > 0.7 else "medium" if scene.risk_score > 0.3 else "low"
                    desc = f"Driving scene {scene.scene_id} with {risk_level} risk level"

                scene_descriptions.append(desc)

            # Create prompt for Claude
            prompt = self.create_naming_prompt(scene_descriptions, naming_strategy, cluster)

            # Call Claude via Bedrock
            category_name = self.call_claude_for_naming(prompt)

            if category_name and self.validate_category_name(category_name):
                logger.info(f"Generated category name: '{category_name}' for cluster {cluster.cluster_id}")
                return category_name
            else:
                logger.warning(f"Invalid category name generated: '{category_name}' - using fallback")
                return self.generate_fallback_name(cluster)

        except Exception as e:
            logger.error(f"Failed to generate category name for cluster {cluster.cluster_id}: {str(e)}")
            return self.generate_fallback_name(cluster)

    def create_naming_prompt(self, scene_descriptions: List[str],
                           naming_strategy: str, cluster: DiscoveredCluster,
                           used_names: List[str] = None) -> str:
        """
        UPDATED: Added used_names to prevent collision
        """
        scene_list = "\n".join([f"- {desc}" for desc in scene_descriptions])

        # Build the blacklist string
        blacklist_str = ""
        if used_names:
            blacklist_str = f"\nCRITICAL: Do NOT use any of these names: {', '.join(used_names)}"

        prompt = f"""These {len(scene_descriptions)} driving scenarios were mathematically clustered together:

{scene_list}

{blacklist_str}

Requirement: Identify the HIDDEN commonality. Look beyond just 'traffic'. Are they all night scenes? Are they construction? Are they highway merges?

Cluster Statistics:
- Total scenes in cluster: {cluster.scene_count}
- Average risk score: {cluster.average_risk_score:.2f}
- Uniqueness score: {cluster.uniqueness_score:.2f}

Rules:
- Return ONLY a descriptive 2-4 word category name.
- Be highly specific. Avoid generic terms like 'Moderate', 'Standard', or 'Routine'.
- The name must be unique from the list above.
- Examples of GOOD names: "Highway Merge Complexity", "Urban Night Driving", "Construction Zone Navigation"

Category name:"""

        return prompt

    def call_claude_for_naming(self, prompt: str) -> Optional[str]:
        """
        Call Claude via AWS Bedrock for category naming
        Following dashboard_api.py patterns for Bedrock integration
        """
        try:
            # Use Claude 3.5 Sonnet for intelligent naming
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 50,  # Short response for category names
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # Lower temperature for more consistent naming
                "top_p": 0.9
            }

            response = self.bedrock_client.invoke_model(
                modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",  # FIXED: Use US inference profile
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body)
            )

            response_data = json.loads(response['body'].read())

            if 'content' in response_data and len(response_data['content']) > 0:
                category_name = response_data['content'][0]['text'].strip()

                # Clean up the response
                category_name = category_name.replace('"', '').replace("'", "")
                category_name = category_name.replace("Category name:", "").strip()

                return category_name

            logger.error("Invalid response structure from Claude")
            return None

        except Exception as e:
            logger.error(f"Failed to call Claude for naming: {str(e)}")
            return None

    def validate_category_name(self, name: str) -> bool:
        """
        Validate generated category name meets requirements
        """
        if not name:
            return False

        # Basic validation rules
        name = name.strip()

        # Check length
        if len(name) < 5 or len(name) > 50:
            return False

        # Check word count (should be 2-4 words)
        words = name.split()
        if len(words) < 2 or len(words) > 4:
            return False

        # Check for reasonable characters (letters, spaces, some punctuation)
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_')
        if not all(c in allowed_chars for c in name):
            return False

        return True

    def generate_fallback_name(self, cluster: DiscoveredCluster) -> str:
        """
        Generate fallback category name when Claude is unavailable or fails
        Based on cluster characteristics and risk level
        """
        try:
            risk_score = cluster.average_risk_score
            scene_count = cluster.scene_count

            # Risk-based naming
            if risk_score > 0.7:
                risk_category = "High Risk"
            elif risk_score > 0.5:
                risk_category = "Moderate Risk"
            elif risk_score > 0.3:
                risk_category = "Low Risk"
            else:
                risk_category = "Routine"

            # Size-based qualifier
            if scene_count > 50:
                size_qualifier = "Frequent"
            elif scene_count > 20:
                size_qualifier = "Common"
            elif scene_count > 10:
                size_qualifier = "Regular"
            else:
                size_qualifier = "Rare"

            fallback_name = f"{size_qualifier} {risk_category} Scenarios"

            logger.info(f"Generated fallback name: '{fallback_name}' for cluster {cluster.cluster_id}")
            return fallback_name

        except Exception as e:
            logger.error(f"Failed to generate fallback name: {str(e)}")
            return f"Discovered Category {cluster.cluster_id}"

    def name_all_clusters(self, discovered_clusters: List[DiscoveredCluster]) -> List[DiscoveredCluster]:
        """
        Generate names for all discovered clusters
        UPDATED: Added anti-repetition logic and rate limiting
        """
        try:
            logger.info(f"Generating names for {len(discovered_clusters)} discovered clusters...")
            import time  # Import for rate limiting

            named_clusters = []
            used_names = []  # TRACK USED NAMES HERE

            for i, cluster in enumerate(discovered_clusters):
                logger.info(f"Naming cluster {i+1}/{len(discovered_clusters)}: {cluster.scene_count} scenes")

                # Get closest centroid scenes for naming
                if cluster.scene_count < 5:
                    centroid_scenes = cluster.scenes  # Send ALL available scenes
                    naming_strategy = "full_cluster"
                else:
                    centroid_scenes = self.get_closest_to_centroid(
                        cluster.scenes,
                        cluster.centroid_behavioral,
                        5
                    )
                    naming_strategy = "centroid_subset"

                # Prepare scene descriptions
                scene_descriptions = []
                for scene in centroid_scenes:
                    desc = scene.description
                    if not desc or desc == f"Scene {scene.scene_id}":
                        # Generate basic description from available metadata
                        risk_level = "high" if scene.risk_score > 0.7 else "medium" if scene.risk_score > 0.3 else "low"
                        desc = f"Driving scene {scene.scene_id} with {risk_level} risk level"
                    scene_descriptions.append(desc)

                # 1. Create prompt with blacklist
                prompt = self.create_naming_prompt(
                    scene_descriptions,
                    naming_strategy,
                    cluster,
                    used_names=used_names
                )

                # 2. Get name from Claude
                category_name = self.call_claude_for_naming(prompt)

                # 3. Validate and save name to blacklist
                if category_name and self.validate_category_name(category_name):
                    used_names.append(category_name)  # Add to blacklist
                    cluster.category_name = category_name
                    logger.info(f"Generated unique category name: '{category_name}' for cluster {cluster.cluster_id}")
                else:
                    # Use fallback if Claude failed or returned invalid name
                    fallback_name = self.generate_fallback_name(cluster)
                    used_names.append(fallback_name)  # Add fallback to blacklist too
                    cluster.category_name = fallback_name
                    logger.warning(f"Using fallback name: '{fallback_name}' for cluster {cluster.cluster_id}")

                named_clusters.append(cluster)

                # Rate limiting: Wait 500ms between Claude calls to prevent throttling
                time.sleep(0.5)  # nosemgrep: arbitrary-sleep - intentional rate limiting for API calls

                # Progress logging for large numbers of clusters
                if (i + 1) % 5 == 0:
                    logger.info(f"Named {i + 1}/{len(discovered_clusters)} clusters...")

            logger.info(f"Cluster naming complete. Used names: {used_names}")
            return named_clusters

        except Exception as e:
            logger.error(f"Failed to name clusters: {str(e)}")
            return discovered_clusters  # Return original clusters with temporary names

# Convenience function for direct usage
def name_discovered_clusters(clusters: List[DiscoveredCluster]) -> List[DiscoveredCluster]:
    """
    Convenience function for naming discovered clusters
    Returns clusters with intelligent category names
    """
    service = CategoryNamingService()
    return service.name_all_clusters(clusters)