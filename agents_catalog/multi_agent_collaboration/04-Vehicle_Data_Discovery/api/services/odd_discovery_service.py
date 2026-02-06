#!/usr/bin/env python3
import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Configure logging (following dashboard_api.py pattern)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Clustering dependencies - handle gracefully if not available
try:
    from sklearn.cluster import HDBSCAN
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    clustering_available = True
except ImportError as e:
    logger.warning(f"Clustering libraries not available: {e}")
    logger.warning("Install with: pip install scikit-learn hdbscan")
    clustering_available = False

# Import our embedding retrieval service
from .embedding_retrieval import SceneEmbeddings, load_all_embeddings

@dataclass
class DiscoveredCluster:
    """Data structure for discovered ODD cluster"""
    cluster_id: int
    category_name: str
    scenes: List[SceneEmbeddings]
    scene_count: int
    average_risk_score: float
    risk_adaptive_target: int
    uniqueness_score: float
    discovery_method: str
    centroid_behavioral: np.ndarray
    centroid_visual: np.ndarray

class OddDiscoveryService:
    """
    True ODD Discovery Service using HDBSCAN clustering
    Discovers natural categories from dual-vector embeddings
    Following patterns from dashboard_api.py for error handling and logging
    """

    def __init__(self):
        """Initialize discovery service"""
        self.clustering_available = clustering_available

    def calculate_risk_adaptive_target(self, cluster_scenes: List[SceneEmbeddings]) -> int:
        """
        Calculate risk-adaptive target using the user's formula:
        Target = Base Significance × (1 + Risk Multiplier)
        """
        if not cluster_scenes:
            return 50  # Default base significance

        try:
            # Calculate average risk score for the cluster
            risk_scores = [scene.risk_score for scene in cluster_scenes]
            avg_risk = np.mean(risk_scores)

            # Base significance - minimum statistical sample size
            base_significance = 50

            # Risk multiplier: scale 0-1 risk to 0-2 multiplier
            risk_multiplier = avg_risk * 2

            # Apply formula
            target = int(base_significance * (1 + risk_multiplier))

            logger.debug(f"Risk-adaptive target calculation: avg_risk={avg_risk:.3f}, target={target}")
            return target

        except Exception as e:
            logger.error(f"Failed to calculate risk-adaptive target: {str(e)}")
            return 50  # Fallback to base significance

    def calculate_uniqueness_score(self, cluster_scenes: List[SceneEmbeddings],
                                 all_embeddings: List[SceneEmbeddings]) -> float:
        """
        Calculate uniqueness score for a cluster
        Higher score means more diverse/unique scenes within the cluster
        """
        if len(cluster_scenes) < 2:
            return 1.0  # Single scene is 100% unique

        try:
            # Extract embeddings for this cluster (use behavioral embeddings for uniqueness)
            cluster_vectors = np.array([scene.cohere_embedding for scene in cluster_scenes])

            # Calculate pairwise distances within cluster
            from sklearn.metrics.pairwise import cosine_distances
            distances = cosine_distances(cluster_vectors)

            # Average distance indicates diversity (higher = more unique)
            avg_distance = np.mean(distances[np.triu_indices_from(distances, k=1)])

            # Convert to 0-1 score (higher = more unique)
            uniqueness_score = min(avg_distance, 1.0)

            return uniqueness_score

        except Exception as e:
            logger.error(f"Failed to calculate uniqueness score: {str(e)}")
            return 0.7  # Default reasonable uniqueness

    def _create_global_fallback_cluster(self, embeddings_data: List[SceneEmbeddings]) -> DiscoveredCluster:
        """
        Create a fallback cluster containing all scenes when HDBSCAN finds no natural clusters.
        This happens when the dataset is homogeneous (which is actually good for training!)
        Uses completely dynamic scene counting - no hardcoded numbers.
        """
        try:
            scene_count = len(embeddings_data)  # Dynamic count
            logger.info(f"Creating global fallback cluster with {scene_count} scenes")

            # Calculate overall statistics - all dynamic
            avg_risk = np.mean([scene.risk_score for scene in embeddings_data])
            risk_adaptive_target = self.calculate_risk_adaptive_target(embeddings_data)
            uniqueness_score = self.calculate_uniqueness_score(embeddings_data, embeddings_data)

            # Calculate global centroids from actual data
            behavioral_vectors = np.array([scene.cohere_embedding for scene in embeddings_data])
            visual_vectors = np.array([scene.cosmos_embedding for scene in embeddings_data])

            centroid_behavioral = np.mean(behavioral_vectors, axis=0)
            centroid_visual = np.mean(visual_vectors, axis=0)

            # Create global cluster with dynamic data
            # FIXED: Convert numpy types to Python native types for JSON serialization
            global_cluster = DiscoveredCluster(
                cluster_id=0,
                category_name="General fleet Behavior",  # Will be refined by Claude naming
                scenes=embeddings_data,
                scene_count=scene_count,  # Dynamic
                average_risk_score=float(avg_risk),  # Convert numpy.float64 to float
                risk_adaptive_target=int(risk_adaptive_target),  # Convert numpy.int64 to int
                uniqueness_score=float(uniqueness_score),  # Convert numpy.float64 to float
                discovery_method="global_fallback_homogeneous",
                centroid_behavioral=centroid_behavioral.tolist(),  # Convert numpy array to list
                centroid_visual=centroid_visual.tolist()  # Convert numpy array to list
            )

            logger.info(f"Global fallback cluster created: {scene_count} scenes, avg risk {avg_risk:.2f}")
            return global_cluster

        except Exception as e:
            logger.error(f"Failed to create global fallback cluster: {str(e)}")
            raise

    def perform_dual_vector_clustering(self, embeddings_data: List[SceneEmbeddings],
                                     min_cluster_size: int = 5) -> List[DiscoveredCluster]:
        """
        Perform HDBSCAN clustering on both behavioral and visual embeddings
        Find clusters that are coherent in both embedding spaces
        """
        if not self.clustering_available:
            logger.error("Clustering libraries not available - cannot perform discovery")
            return []

        if len(embeddings_data) < min_cluster_size:
            logger.warning(f"Not enough scenes ({len(embeddings_data)}) for clustering (min: {min_cluster_size})")
            return []

        try:
            logger.info(f"Starting dual-vector clustering on {len(embeddings_data)} scenes...")

            # Extract embedding matrices
            behavioral_vectors = np.array([scene.cohere_embedding for scene in embeddings_data])
            visual_vectors = np.array([scene.cosmos_embedding for scene in embeddings_data])

            logger.info(f"Behavioral embeddings shape: {behavioral_vectors.shape}")
            logger.info(f"Visual embeddings shape: {visual_vectors.shape}")

            # Validate and clean embedding data (fix inf/NaN issue)
            behavioral_has_invalid = np.any(~np.isfinite(behavioral_vectors))
            visual_has_invalid = np.any(~np.isfinite(visual_vectors))

            if behavioral_has_invalid or visual_has_invalid:
                logger.warning(f"Invalid values detected - behavioral: {behavioral_has_invalid}, visual: {visual_has_invalid}")

                # Count and log details about invalid values
                behavioral_inf_count = np.sum(np.isinf(behavioral_vectors))
                behavioral_nan_count = np.sum(np.isnan(behavioral_vectors))
                visual_inf_count = np.sum(np.isinf(visual_vectors))
                visual_nan_count = np.sum(np.isnan(visual_vectors))

                logger.info(f"Behavioral: {behavioral_inf_count} inf values, {behavioral_nan_count} NaN values")
                logger.info(f"Visual: {visual_inf_count} inf values, {visual_nan_count} NaN values")

                # Clean invalid values by replacing with 0 (conservative approach)
                behavioral_vectors = np.nan_to_num(behavioral_vectors, nan=0.0, posinf=0.0, neginf=0.0)
                visual_vectors = np.nan_to_num(visual_vectors, nan=0.0, posinf=0.0, neginf=0.0)

                logger.info("Cleaned embedding vectors by replacing inf/NaN with 0.0")
            else:
                logger.info("Embedding data validation passed - no inf/NaN values detected")

            # ROBUST PROCESSING: Fix rank deficiency and zero variance issues

            # 1. REMOVE "DEAD" DIMENSIONS (Variance Filtering)
            # If a dimension has 0 variance (same value in all scenes), it breaks StandardScaler
            def remove_constant_features(X):
                """Remove features with zero or near-zero variance"""
                std = np.std(X, axis=0)
                valid_features = std > 1e-6
                removed_count = np.sum(~valid_features)
                if removed_count > 0:
                    logger.warning(f"Removed {removed_count} constant/near-zero variance features")
                return X[:, valid_features]

            logger.info("Applying variance filtering to remove constant features...")
            behavioral_vectors_filtered = remove_constant_features(behavioral_vectors)
            visual_vectors_filtered = remove_constant_features(visual_vectors)

            logger.info(f"After variance filtering - behavioral: {behavioral_vectors_filtered.shape}, visual: {visual_vectors_filtered.shape}")

            # 2. ROBUST SCALING
            scaler_behavioral = StandardScaler()
            scaler_visual = StandardScaler()

            # Using fit_transform - if this still produces NaNs, we fill them with 0
            behavioral_normalized = np.nan_to_num(scaler_behavioral.fit_transform(behavioral_vectors_filtered))
            visual_normalized = np.nan_to_num(scaler_visual.fit_transform(visual_vectors_filtered))

            logger.info("Scaling complete with NaN safety net applied")

            # 3. DYNAMIC PCA (The "Rank Deficiency" Fix)
            # Instead of asking for fixed components, we ask for "95% of the information"
            # This automatically handles redundant dimensions by dropping them
            logger.info("Applying dynamic PCA with 95% variance retention...")

            try:
                pca_behavioral = PCA(n_components=0.95, svd_solver='full')
                pca_visual = PCA(n_components=0.95, svd_solver='full')

                behavioral_reduced = pca_behavioral.fit_transform(behavioral_normalized)
                visual_reduced = pca_visual.fit_transform(visual_normalized)

                logger.info(f"✅ PCA complete. Behavioral dims: {behavioral_reduced.shape[1]}, Visual dims: {visual_reduced.shape[1]}")
                logger.info(f"Behavioral explained variance: {np.sum(pca_behavioral.explained_variance_ratio_):.3f}")
                logger.info(f"Visual explained variance: {np.sum(pca_visual.explained_variance_ratio_):.3f}")

            except Exception as e:
                logger.error(f"❌ PCA still failed, using raw normalized data as fallback: {e}")
                behavioral_reduced = behavioral_normalized
                visual_reduced = visual_normalized
                logger.warning("Using raw normalized embeddings (no dimensionality reduction)")

            # L2-NORMALIZATION: Convert to unit vectors for cosine equivalence
            # This enables euclidean distance to behave like cosine distance on the unit sphere
            from sklearn.preprocessing import normalize
            behavioral_l2_normalized = normalize(behavioral_reduced, norm='l2')
            visual_l2_normalized = normalize(visual_reduced, norm='l2')

            logger.info("✅ L2-normalization complete - vectors now on unit sphere for cosine equivalence")

            # Perform HDBSCAN clustering on behavioral embeddings (primary)
            # Using euclidean metric on L2-normalized data = cosine clustering behavior
            clusterer_behavioral = HDBSCAN(
                min_cluster_size=min_cluster_size,  # 5
                min_samples=max(3, min_cluster_size // 2),  # Dynamic: 3 (original logic)
                cluster_selection_epsilon=0.1,  # Only merges very close points (original strict)
                metric='euclidean'  # Euclidean on unit sphere = cosine behavior (triangle inequality satisfied)
            )

            behavioral_labels = clusterer_behavioral.fit_predict(behavioral_l2_normalized)

            # Get unique cluster IDs (excluding noise: -1)
            unique_clusters = set(behavioral_labels)
            unique_clusters.discard(-1)  # Remove noise cluster

            logger.info(f"HDBSCAN found {len(unique_clusters)} behavioral clusters (excluding noise)")

            if len(unique_clusters) == 0:
                logger.warning("No natural clusters found - falling back to global cluster for homogeneous dataset")
                # Create one single cluster containing ALL scenes (resilience fallback)
                return [self._create_global_fallback_cluster(embeddings_data)]

            discovered_clusters = []

            for cluster_id in unique_clusters:
                # Get scenes in this cluster
                cluster_mask = behavioral_labels == cluster_id
                cluster_scenes = [embeddings_data[i] for i in np.where(cluster_mask)[0]]

                if len(cluster_scenes) == 0:
                    continue

                logger.info(f"Processing cluster {cluster_id}: {len(cluster_scenes)} scenes")

                # Calculate cluster properties
                avg_risk = np.mean([scene.risk_score for scene in cluster_scenes])
                risk_adaptive_target = self.calculate_risk_adaptive_target(cluster_scenes)
                uniqueness_score = self.calculate_uniqueness_score(cluster_scenes, embeddings_data)

                # Calculate centroids
                cluster_behavioral_vectors = behavioral_vectors[cluster_mask]
                cluster_visual_vectors = visual_vectors[cluster_mask]

                centroid_behavioral = np.mean(cluster_behavioral_vectors, axis=0)
                centroid_visual = np.mean(cluster_visual_vectors, axis=0)

                # Create discovered cluster object (category name will be generated later)
                # FIXED: Convert numpy types to Python native types for JSON serialization
                discovered_cluster = DiscoveredCluster(
                    cluster_id=int(cluster_id),  # Convert numpy.int64 to int
                    category_name=f"cluster_{cluster_id}",  # Temporary name
                    scenes=cluster_scenes,
                    scene_count=len(cluster_scenes),
                    average_risk_score=float(avg_risk),  # Convert numpy.float64 to float
                    risk_adaptive_target=int(risk_adaptive_target),  # Convert numpy.int64 to int
                    uniqueness_score=float(uniqueness_score),  # Convert numpy.float64 to float
                    discovery_method="hdbscan_dual_vector",
                    centroid_behavioral=centroid_behavioral.tolist(),  # Convert numpy array to list
                    centroid_visual=centroid_visual.tolist()  # Convert numpy array to list
                )

                discovered_clusters.append(discovered_cluster)

            # Sort clusters by size (largest first)
            discovered_clusters.sort(key=lambda c: c.scene_count, reverse=True)

            logger.info(f"Discovery complete: {len(discovered_clusters)} clusters discovered")

            # Log cluster summary
            for cluster in discovered_clusters:
                logger.info(f"Cluster {cluster.cluster_id}: {cluster.scene_count} scenes, "
                          f"avg_risk={cluster.average_risk_score:.3f}, "
                          f"target={cluster.risk_adaptive_target}, "
                          f"uniqueness={cluster.uniqueness_score:.3f}")

            return discovered_clusters

        except Exception as e:
            # Provide specific error details for better debugging
            error_msg = f"Dual-vector clustering failed: {str(e)}"
            error_type = type(e).__name__

            # Add specific failure context based on error type
            if "inf" in str(e).lower() or "nan" in str(e).lower():
                error_msg += " | Root cause: Invalid values (inf/NaN) in embeddings - check data pipeline"
            elif "array" in str(e).lower() and "shape" in str(e).lower():
                error_msg += " | Root cause: Dimensional mismatch in embedding arrays"
            elif "rank" in str(e).lower() or "singular" in str(e).lower():
                error_msg += " | Root cause: Matrix rank deficiency - insufficient unique patterns"
            elif "memory" in str(e).lower() or "allocation" in str(e).lower():
                error_msg += " | Root cause: Insufficient memory for clustering large dataset"
            elif "hdbscan" in str(e).lower():
                error_msg += " | Root cause: HDBSCAN clustering algorithm failure - check parameters"
            elif "pca" in str(e).lower():
                error_msg += " | Root cause: PCA dimensionality reduction failure"
            else:
                error_msg += f" | Error type: {error_type}"

            logger.error(error_msg)
            # Return error info for upstream handling
            return {"error": error_msg, "error_type": error_type}

    def discover_natural_categories(self, min_cluster_size: int = 5, embeddings_data: List[SceneEmbeddings] = None) -> List[DiscoveredCluster]:
        """
        Main discovery function - loads embeddings (if not provided) and performs clustering
        Returns discovered ODD categories with risk-adaptive targets

        Args:
            min_cluster_size: Minimum cluster size for HDBSCAN
            embeddings_data: Pre-loaded embeddings (optional) - prevents duplicate loading
        """
        try:
            logger.info("Starting natural ODD category discovery...")

            if not self.clustering_available:
                return []

            # Load embeddings only if not already provided (prevents duplicate loading)
            if embeddings_data is None:
                logger.info("No pre-loaded embeddings provided - loading from S3...")
                embeddings_data = load_all_embeddings()

                if not embeddings_data:
                    logger.error("No embeddings data loaded - cannot perform discovery")
                    return []

                logger.info(f"Loaded {len(embeddings_data)} scenes for clustering (dynamic count)")
            else:
                logger.info(f"Using pre-loaded embeddings: {len(embeddings_data)} scenes (performance optimized)")

            # Perform clustering
            discovered_clusters = self.perform_dual_vector_clustering(
                embeddings_data,
                min_cluster_size=min_cluster_size
            )

            if not discovered_clusters:
                logger.warning("No clusters discovered")
                return []

            logger.info(f"Natural category discovery complete: {len(discovered_clusters)} categories found")
            return discovered_clusters

        except Exception as e:
            logger.error(f"Natural category discovery failed: {str(e)}")
            return []

    def get_discovery_summary(self) -> Dict:
        """
        Get summary of discovery capabilities and status
        Useful for health checks and debugging
        """
        try:
            from .embedding_retrieval import get_current_dataset_size

            return {
                "clustering_available": self.clustering_available,
                "current_dataset_size": get_current_dataset_size(),
                "min_cluster_size_recommended": 5,
                "discovery_method": "hdbscan_dual_vector",
                "supported_embeddings": ["cohere_1536", "cosmos_768"],
                "risk_adaptive_targets": True,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get discovery summary: {str(e)}")
            return {"error": str(e), "clustering_available": False}

# Convenience function for direct usage
def discover_odd_categories(min_cluster_size: int = 5, embeddings_data: List[SceneEmbeddings] = None) -> List[DiscoveredCluster]:
    """
    Convenience function for discovering ODD categories
    Returns list of discovered clusters with risk-adaptive targets

    Args:
        min_cluster_size: Minimum cluster size for HDBSCAN
        embeddings_data: Pre-loaded embeddings (optional) - prevents duplicate loading
    """
    service = OddDiscoveryService()
    return service.discover_natural_categories(min_cluster_size=min_cluster_size, embeddings_data=embeddings_data)