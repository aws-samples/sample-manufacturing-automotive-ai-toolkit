#!/usr/bin/env python3
"""
Diagnostic script to identify the root cause of inf/NaN values in embedding processing.
This script systematically tests each step of the pipeline to find where inf/NaN is introduced.
"""

import numpy as np
import logging
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from shared.embedding_retrieval import load_all_embeddings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_array_health(data, name):
    """Analyze array for inf/NaN values and statistical properties"""
    finite_count = np.sum(np.isfinite(data))
    inf_count = np.sum(np.isinf(data))
    nan_count = np.sum(np.isnan(data))
    total_elements = data.size

    stats = {
        'name': name,
        'shape': data.shape,
        'total_elements': total_elements,
        'finite_count': finite_count,
        'inf_count': inf_count,
        'nan_count': nan_count,
        'has_invalid': inf_count > 0 or nan_count > 0,
        'min': np.min(data[np.isfinite(data)]) if finite_count > 0 else None,
        'max': np.max(data[np.isfinite(data)]) if finite_count > 0 else None,
        'mean': np.mean(data[np.isfinite(data)]) if finite_count > 0 else None,
        'std': np.std(data[np.isfinite(data)]) if finite_count > 0 else None
    }

    logger.info(f"=== {name} Analysis ===")
    logger.info(f"Shape: {stats['shape']}")
    logger.info(f"Total elements: {stats['total_elements']}")
    logger.info(f"Finite: {stats['finite_count']}, Inf: {stats['inf_count']}, NaN: {stats['nan_count']}")
    if stats['has_invalid']:
        logger.warning(f"❌ INVALID VALUES DETECTED in {name}")
    else:
        logger.info(f"✅ Clean data in {name}")

    if finite_count > 0:
        logger.info(f"Stats (finite only): min={stats['min']:.6f}, max={stats['max']:.6f}, mean={stats['mean']:.6f}, std={stats['std']:.6f}")

    return stats

def test_standardscaler_conditions(data, name):
    """Test StandardScaler under various conditions to identify inf/NaN triggers"""
    logger.info(f"\n🔍 Testing StandardScaler conditions for {name}")

    # Check for zero variance features (division by zero trigger)
    feature_variances = np.var(data, axis=0)
    zero_var_features = np.sum(feature_variances == 0)
    very_small_var_features = np.sum(feature_variances < 1e-10)

    logger.info(f"Zero variance features: {zero_var_features}")
    logger.info(f"Very small variance features (< 1e-10): {very_small_var_features}")

    if zero_var_features > 0:
        logger.warning("❌ ZERO VARIANCE FEATURES DETECTED - StandardScaler division by zero risk!")
        zero_var_indices = np.where(feature_variances == 0)[0]
        logger.warning(f"Zero variance feature indices: {zero_var_indices[:10]}...")  # Show first 10

        # Analyze the zero variance features
        for i in zero_var_indices[:5]:  # Check first 5
            unique_values = np.unique(data[:, i])
            logger.warning(f"Feature {i}: unique values = {unique_values}")

    if very_small_var_features > 0:
        logger.warning(f"❌ VERY SMALL VARIANCE FEATURES - Potential numerical instability!")
        small_var_indices = np.where(feature_variances < 1e-10)[0]
        logger.warning(f"Small variance feature indices: {small_var_indices[:10]}...")

        for i in small_var_indices[:3]:  # Check first 3
            logger.warning(f"Feature {i}: variance = {feature_variances[i]:.2e}")

    # Test StandardScaler with this specific data
    try:
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(data)
        analyze_array_health(scaled_data, f"{name}_scaled")

        # Check scaler parameters
        logger.info(f"Scaler mean range: [{np.min(scaler.mean_):.6f}, {np.max(scaler.mean_):.6f}]")
        logger.info(f"Scaler scale range: [{np.min(scaler.scale_):.6f}, {np.max(scaler.scale_):.6f}]")

        # Check for problematic scale values
        problematic_scales = np.sum(scaler.scale_ < 1e-10)
        if problematic_scales > 0:
            logger.warning(f"❌ {problematic_scales} features have extremely small scale values!")

        return scaled_data, True
    except Exception as e:
        logger.error(f"❌ StandardScaler FAILED on {name}: {e}")
        return None, False

def test_pca_conditions(data, name, n_components):
    """Test PCA under various conditions to identify inf/NaN triggers"""
    logger.info(f"\n🔍 Testing PCA conditions for {name} (components: {n_components})")

    # Check data characteristics that could cause PCA issues
    rank = np.linalg.matrix_rank(data)
    logger.info(f"Data matrix rank: {rank} (vs shape: {data.shape})")

    if rank < min(data.shape):
        logger.warning(f"❌ RANK DEFICIENCY DETECTED - Matrix rank {rank} < min dimension {min(data.shape)}")

    # Check condition number
    try:
        # Use SVD to compute condition number safely
        U, s, Vt = np.linalg.svd(data, full_matrices=False)
        condition_number = s[0] / s[-1] if len(s) > 0 and s[-1] != 0 else float('inf')
        logger.info(f"Condition number: {condition_number:.2e}")

        if condition_number > 1e12:
            logger.warning(f"❌ HIGH CONDITION NUMBER - Numerical instability risk!")

        # Check for zero/near-zero singular values
        zero_singular_values = np.sum(s < 1e-14)
        if zero_singular_values > 0:
            logger.warning(f"❌ {zero_singular_values} near-zero singular values detected!")

    except Exception as e:
        logger.error(f"SVD analysis failed: {e}")

    # Test PCA with this specific data
    try:
        pca = PCA(n_components=n_components)
        pca_data = pca.fit_transform(data)
        analyze_array_health(pca_data, f"{name}_pca")

        # Check explained variance
        logger.info(f"Explained variance ratio: {pca.explained_variance_ratio_[:5]}")  # First 5 components

        return pca_data, True
    except Exception as e:
        logger.error(f"❌ PCA FAILED on {name}: {e}")
        return None, False

def identify_problematic_scenes(embeddings_data):
    """Identify specific scenes that might contain problematic embeddings"""
    logger.info("\n🔍 Analyzing individual scene embeddings for anomalies")

    problematic_scenes = []

    for i, scene in enumerate(embeddings_data[:10]):  # Check first 10 scenes
        scene_id = scene.scene_id

        # Check Cohere embedding
        cohere_health = analyze_array_health(scene.cohere_embedding, f"Scene_{scene_id}_Cohere")
        if cohere_health['has_invalid']:
            problematic_scenes.append((scene_id, 'cohere', cohere_health))

        # Check Cosmos embedding
        cosmos_health = analyze_array_health(scene.cosmos_embedding, f"Scene_{scene_id}_Cosmos")
        if cosmos_health['has_invalid']:
            problematic_scenes.append((scene_id, 'cosmos', cosmos_health))

    if problematic_scenes:
        logger.error(f"❌ Found {len(problematic_scenes)} scenes with invalid embeddings:")
        for scene_id, embedding_type, health in problematic_scenes:
            logger.error(f"  - {scene_id} ({embedding_type}): {health['inf_count']} inf, {health['nan_count']} nan")
    else:
        logger.info("✅ First 10 scenes have clean embeddings")

    return problematic_scenes

def main():
    """Main diagnostic function"""
    logger.info("🚀 Starting inf/NaN root cause investigation...")

    try:
        # Load embeddings
        logger.info("\n📊 Loading embeddings...")
        embeddings_data = load_all_embeddings()

        if not embeddings_data:
            logger.error("❌ No embeddings loaded - cannot diagnose")
            return

        logger.info(f"✅ Loaded {len(embeddings_data)} scene embeddings")

        # Check individual scenes first
        problematic_scenes = identify_problematic_scenes(embeddings_data)

        # Extract embedding matrices
        logger.info("\n📊 Extracting embedding matrices...")
        behavioral_vectors = np.array([scene.cohere_embedding for scene in embeddings_data])
        visual_vectors = np.array([scene.cosmos_embedding for scene in embeddings_data])

        # Analyze raw embeddings
        behavioral_health = analyze_array_health(behavioral_vectors, "Raw_Behavioral_Embeddings")
        visual_health = analyze_array_health(visual_vectors, "Raw_Visual_Embeddings")

        # If raw embeddings are clean, test processing steps
        if not behavioral_health['has_invalid'] and not visual_health['has_invalid']:
            logger.info("✅ Raw embeddings are clean - testing processing pipeline...")

            # Test StandardScaler
            behavioral_scaled, behavioral_scaler_ok = test_standardscaler_conditions(behavioral_vectors, "Behavioral")
            visual_scaled, visual_scaler_ok = test_standardscaler_conditions(visual_vectors, "Visual")

            # Test PCA if StandardScaler succeeded
            if behavioral_scaler_ok and behavioral_scaled is not None:
                n_components = min(100, behavioral_vectors.shape[1])
                test_pca_conditions(behavioral_scaled, "Behavioral", n_components)

            if visual_scaler_ok and visual_scaled is not None:
                n_components = min(50, visual_vectors.shape[1])
                test_pca_conditions(visual_scaled, "Visual", n_components)

        else:
            logger.error("❌ Raw embeddings already contain invalid values!")
            if behavioral_health['has_invalid']:
                logger.error(f"Behavioral: {behavioral_health['inf_count']} inf, {behavioral_health['nan_count']} nan")
            if visual_health['has_invalid']:
                logger.error(f"Visual: {visual_health['inf_count']} inf, {visual_health['nan_count']} nan")

    except Exception as e:
        logger.error(f"❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()