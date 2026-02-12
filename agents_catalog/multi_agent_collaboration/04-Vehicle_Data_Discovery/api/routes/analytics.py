"""Analytics routes - coverage, ODD discovery, and related endpoints."""
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter

from dependencies import s3, s3vectors, s3vectors_available, BUCKET, VECTOR_BUCKET, INDICES_CONFIG
from services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])

DEFAULT_ANALYTICS_ENGINE = "behavioral"

# Import clustering services if available
try:
    from services.odd_discovery_service import discover_odd_categories
    from services.category_naming_service import name_discovered_clusters, CategoryNamingService
    clustering_services_available = True
except ImportError:
    clustering_services_available = False


def calculate_safety_weighted_target(cluster):
    """Safety-grade target calculation for autonomous driving."""
    try:
        total_scenes = cluster.scene_count
        risk_score = getattr(cluster, 'average_risk_score', 0.5)
        uniqueness_score = getattr(cluster, 'uniqueness_score', 0.7)

        if risk_score > 0.8:
            target_multiplier = 1.0
        elif risk_score >= 0.5:
            target_multiplier = 0.8
        else:
            target_multiplier = uniqueness_score * 0.7

        safety_target = int(total_scenes * max(uniqueness_score, target_multiplier))
        return {
            "test_target": safety_target,
            "dto_value": safety_target * 30,
            "risk_score": risk_score,
            "target_multiplier": target_multiplier
        }
    except Exception as e:
        logger.error(f"Safety calculation failed: {e}")
        return {"test_target": getattr(cluster, 'scene_count', 50), "dto_value": 1500}


def analyze_uniqueness_within_category(concept_description: str, similarity_threshold: float = 0.35, pipeline_scenes_filter: set = None) -> dict:
    """Analyze uniqueness/redundancy within a discovered ODD category."""
    if not s3vectors_available:
        return {"uniqueness_score": 0.0, "redundancy_ratio": 0.0, "error": "S3 Vectors unavailable"}

    try:
        enhanced_query = f"Autonomous vehicle driving scenario involving {concept_description}"
        query_vector = generate_embedding(enhanced_query, DEFAULT_ANALYTICS_ENGINE)

        if not query_vector:
            return {"unique_scenes": [], "uniqueness_score": 0.0, "error": "Failed to generate embedding"}

        results = s3vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDICES_CONFIG[DEFAULT_ANALYTICS_ENGINE]["name"],
            queryVector={"float32": query_vector},
            topK=100,
            returnDistance=True,
            returnMetadata=True
        )

        category_scenes = []
        for match in results.get("vectors", []):
            distance = match.get("distance", 1.0)
            similarity_to_concept = 1.0 - distance

            if similarity_to_concept >= similarity_threshold:
                scene_id = match.get("metadata", {}).get("scene_id", "unknown")
                if pipeline_scenes_filter is None or scene_id in pipeline_scenes_filter:
                    category_scenes.append({
                        "scene_id": scene_id,
                        "similarity_to_concept": similarity_to_concept
                    })

        if len(category_scenes) < 2:
            return {"uniqueness_score": 1.0, "redundancy_ratio": 0.0, "unique_scenes": len(category_scenes), "total_scenes": len(category_scenes)}

        high_similarity_scenes = [s for s in category_scenes if s["similarity_to_concept"] >= 0.6]
        medium_similarity_scenes = [s for s in category_scenes if 0.4 <= s["similarity_to_concept"] < 0.6]
        low_similarity_scenes = [s for s in category_scenes if 0.35 <= s["similarity_to_concept"] < 0.4]

        total_scenes = len(category_scenes)
        estimated_unique_scenes = (
            len(low_similarity_scenes) * 0.9 +
            len(medium_similarity_scenes) * 0.7 +
            len(high_similarity_scenes) * 0.5
        )

        uniqueness_score = estimated_unique_scenes / total_scenes if total_scenes > 0 else 0.0
        redundancy_ratio = 1.0 - uniqueness_score

        if uniqueness_score >= 0.8:
            uniqueness_quality = "excellent"
        elif uniqueness_score >= 0.6:
            uniqueness_quality = "good"
        elif uniqueness_score >= 0.4:
            uniqueness_quality = "moderate"
        else:
            uniqueness_quality = "poor"

        return {
            "total_scenes": total_scenes,
            "estimated_unique_scenes": round(estimated_unique_scenes, 1),
            "uniqueness_score": round(uniqueness_score, 3),
            "redundancy_ratio": round(redundancy_ratio, 3),
            "uniqueness_quality": uniqueness_quality,
            "similarity_distribution": {
                "high_similarity_count": len(high_similarity_scenes),
                "medium_similarity_count": len(medium_similarity_scenes),
                "low_similarity_count": len(low_similarity_scenes)
            },
            "dto_value_estimate": round(estimated_unique_scenes * 30, 1)
        }

    except Exception as e:
        logger.error(f"Uniqueness analysis failed: {e}")
        return {"uniqueness_score": 0.0, "redundancy_ratio": 0.0, "error": str(e)}


def get_semantic_coverage_count(concept_description: str, similarity_threshold: float = 0.35) -> int:
    """Count scenes matching a semantic concept using vector similarity."""
    try:
        enhanced_query = f"Autonomous vehicle driving scenario involving {concept_description}"
        vector = generate_embedding(enhanced_query, DEFAULT_ANALYTICS_ENGINE)
        if not vector:
            logger.warning(f"Failed to generate embedding for: {concept_description}")
            return 0
        results = s3vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDICES_CONFIG[DEFAULT_ANALYTICS_ENGINE]["name"],
            queryVector={"float32": vector},
            topK=100,  # S3 Vectors max is 100
            returnMetadata=True,
            returnDistance=True
        )
        count = len([r for r in results.get("vectors", []) if 1.0 - r.get("distance", 1.0) >= similarity_threshold])
        logger.info(f"Coverage count for '{concept_description}': {count}")
        return count
    except Exception as e:
        logger.error(f"Semantic coverage count failed for '{concept_description}': {e}")
        return 0


@router.get("/coverage-debug")
def debug_coverage():
    """Debug endpoint for coverage analysis"""
    try:
        # Test the actual function
        urban_count = get_semantic_coverage_count("city driving with traffic lights and pedestrians")
        
        test_query = "Autonomous vehicle driving scenario involving city driving with traffic lights and pedestrians"
        vector = generate_embedding(test_query, DEFAULT_ANALYTICS_ENGINE)
        if not vector:
            return {"error": "Failed to generate embedding", "vector_length": 0}
        
        results = s3vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDICES_CONFIG[DEFAULT_ANALYTICS_ENGINE]["name"],
            queryVector={"float32": vector},
            topK=100,
            returnMetadata=True,
            returnDistance=True
        )
        
        matches = []
        for r in results.get("vectors", []):
            score = 1.0 - r.get("distance", 1.0)
            matches.append({"scene_id": r.get("metadata", {}).get("scene_id"), "score": score})
        
        return {
            "urban_count_from_function": urban_count,
            "vector_length": len(vector),
            "results_count": len(results.get("vectors", [])),
            "matches": matches[:10],
            "above_threshold": len([m for m in matches if m["score"] >= 0.35])
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.get("/coverage")
def get_dataset_coverage():
    """Coverage Matrix - Semantic Analysis"""
    try:
        semantic_concepts = {
            "Highway": "high-speed highway driving with multiple lanes",
            "Urban": "city driving with traffic lights and pedestrians",
            "Construction": "construction zones with barriers and cones",
            "Night": "nighttime driving with limited visibility",
            "Rain": "rainy weather with wet roads",
            "Pedestrian": "pedestrians crossing streets",
            "Motorcycle": "motorcycles sharing roads"
        }

        counts = {}
        total_scenes = 0

        # Sequential calls - ThreadPoolExecutor was causing issues
        for cat, desc in semantic_concepts.items():
            counts[cat] = get_semantic_coverage_count(desc)

        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=BUCKET, Prefix="pipeline-results/", Delimiter='/'):
            total_scenes += len([p for p in page.get('CommonPrefixes', []) if 'scene-' in p['Prefix']])

        targets = {
            "Highway": max(1, int(total_scenes * 0.40)),
            "Urban": max(1, int(total_scenes * 0.25)),
            "Construction": max(1, int(total_scenes * 0.05)),
            "Night": max(1, int(total_scenes * 0.10)),
            "Rain": max(1, int(total_scenes * 0.05)),
            "Pedestrian": max(1, int(total_scenes * 0.08)),
            "Motorcycle": max(1, int(total_scenes * 0.04))
        }

        coverage_report = []
        for category, target in targets.items():
            current = counts.get(category, 0)
            pct = (current / target * 100) if target > 0 else 0
            status = "HEALTHY" if pct >= 90 else "WARNING" if pct >= 50 else "CRITICAL"
            coverage_report.append({
                "category": category, "current": current, "target": target,
                "gap": max(0, target - current), "percentage": round(pct, 1), "status": status
            })

        coverage_report.sort(key=lambda x: x['percentage'])
        return {
            "coverage_targets": coverage_report,
            "total_scenes": total_scenes,
            "critical_gaps": [r for r in coverage_report if r['status'] == 'CRITICAL'],
            "healthy_categories": [r for r in coverage_report if r['status'] == 'HEALTHY']
        }
    except Exception as e:
        logger.error(f"Coverage analysis error: {e}")
        return {"coverage_targets": [], "total_scenes": 0}


@router.get("/odd-discovery")
def get_odd_discovery():
    """ODD Discovery - Natural category discovery"""
    if clustering_services_available:
        try:
            clusters = discover_odd_categories(min_cluster_size=5)
            if clusters:
                named = name_discovered_clusters(clusters)
                categories = [{
                    "category": c.category_name,
                    "scene_count": c.scene_count,
                    "average_risk_score": c.average_risk_score,
                    "uniqueness_score": c.uniqueness_score,
                    "discovery_method": c.discovery_method
                } for c in named]
                return {"discovered_categories": categories, "total_categories_discovered": len(categories)}
        except Exception as e:
            logger.error(f"ODD discovery failed: {e}")
    return {"discovered_categories": [], "total_categories_discovered": 0, "message": "Clustering unavailable"}


@router.get("/odd-similarity-analysis")
def get_odd_similarity_analysis():
    """ODD Similarity Analysis"""
    return {"analysis": "pending", "message": "Use /search for similarity queries"}


@router.get("/odd-uniqueness-analysis")
def get_odd_uniqueness_analysis():
    """True ODD Uniqueness Analysis using HDBSCAN clustering."""
    if not clustering_services_available:
        logger.warning("Clustering services unavailable - using legacy analysis")
        return _legacy_odd_uniqueness_analysis()

    try:
        # Check for cached discovery results
        try:
            from discovery_status_manager import discovery_status_manager
            recent_jobs = discovery_status_manager.list_jobs(limit=5)

            for job in recent_jobs:
                if job.get("status") == "completed" and job.get("discovered_categories") and job["discovered_categories"].get("uniqueness_results"):
                    logger.info(f"Using cached discovery results from job: {job['job_id']}")
                    return {
                        "analysis_method": "hdbscan_clustering_cached",
                        "analysis_timestamp": job.get("completed_at", datetime.utcnow().isoformat()),
                        "cache_source": f"job_{job['job_id']}",
                        **job["discovered_categories"]
                    }
        except Exception as cache_error:
            logger.warning(f"Cache check failed: {cache_error}")

        # No cached results - perform live clustering
        discovered_clusters = discover_odd_categories(min_cluster_size=5)

        if not discovered_clusters:
            return _legacy_odd_uniqueness_analysis()

        named_clusters = name_discovered_clusters(discovered_clusters)

        uniqueness_results = []
        total_scenes_analyzed = 0
        total_unique_scenes = 0

        for cluster in named_clusters:
            safety_result = calculate_safety_weighted_target(cluster)
            total_scenes = cluster.scene_count
            estimated_unique = safety_result["test_target"]

            quality = "excellent" if cluster.uniqueness_score >= 0.8 else "good" if cluster.uniqueness_score >= 0.7 else "moderate" if cluster.uniqueness_score >= 0.5 else "poor"

            high_sim_count = int(total_scenes * (1 - cluster.uniqueness_score) * 0.6)
            medium_sim_count = int(total_scenes * (1 - cluster.uniqueness_score) * 0.4)
            low_sim_count = total_scenes - high_sim_count - medium_sim_count

            representative_scene_id = None
            try:
                naming_service = CategoryNamingService()
                representative_scene = naming_service.get_most_representative_scene(cluster)
                if representative_scene:
                    representative_scene_id = representative_scene.scene_id
                elif cluster.scenes:
                    representative_scene_id = cluster.scenes[0].scene_id
            except:
                if hasattr(cluster, 'scenes') and cluster.scenes:
                    representative_scene_id = cluster.scenes[0].scene_id

            uniqueness_results.append({
                "category": cluster.category_name,
                "description": f"Naturally discovered category with {total_scenes} scenes and average risk score {cluster.average_risk_score:.2f}",
                "total_scenes": total_scenes,
                "estimated_unique_scenes": round(estimated_unique, 1),
                "uniqueness_score": round(cluster.uniqueness_score, 3),
                "redundancy_ratio": round(1.0 - cluster.uniqueness_score, 3),
                "uniqueness_quality": quality,
                "dto_value_estimate": int(estimated_unique * 30),
                "representative_scene_id": representative_scene_id,
                "similarity_distribution": {
                    "high_similarity_count": high_sim_count,
                    "medium_similarity_count": medium_sim_count,
                    "low_similarity_count": max(0, low_sim_count)
                }
            })

            total_scenes_analyzed += total_scenes
            total_unique_scenes += estimated_unique

        uniqueness_results.sort(key=lambda x: x["dto_value_estimate"], reverse=True)

        overall_uniqueness_ratio = total_unique_scenes / total_scenes_analyzed if total_scenes_analyzed > 0 else 0.0
        naive_dto_cost = total_scenes_analyzed * 30
        intelligent_dto_cost = total_unique_scenes * 30
        estimated_savings = naive_dto_cost - intelligent_dto_cost

        return {
            "analysis_method": "hdbscan_clustering_uniqueness_analysis",
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "total_categories_analyzed": len(uniqueness_results),
            "total_scenes_analyzed": int(total_scenes_analyzed),
            "total_unique_scenes_estimated": round(total_unique_scenes, 1),
            "overall_uniqueness_ratio": round(overall_uniqueness_ratio, 3),
            "overall_redundancy_ratio": round(1.0 - overall_uniqueness_ratio, 3),
            "dto_cost_per_scene": 30,
            "dto_savings_estimate": {
                "naive_cost_usd": int(naive_dto_cost),
                "intelligent_cost_usd": int(intelligent_dto_cost),
                "estimated_savings_usd": int(estimated_savings),
                "efficiency_gain_percent": round((estimated_savings / naive_dto_cost * 100), 1) if naive_dto_cost > 0 else 0.0
            },
            "uniqueness_results": uniqueness_results,
            "analysis_quality": "high" if overall_uniqueness_ratio > 0.6 else "medium" if overall_uniqueness_ratio > 0.4 else "low"
        }

    except Exception as e:
        logger.error(f"ODD uniqueness analysis failed: {e}")
        return _legacy_odd_uniqueness_analysis()


def _legacy_odd_uniqueness_analysis():
    """Legacy predefined uniqueness analysis (fallback when clustering unavailable)."""
    try:
        discovery_concepts = {
            "rainy_weather": "rainy weather driving with wet roads and precipitation",
            "nighttime_driving": "nighttime driving with limited visibility and darkness",
            "construction_zones": "construction zones with barriers and work activity",
            "urban_intersections": "city intersections with traffic lights and pedestrians",
            "highway_driving": "high-speed highway driving with multiple lanes",
            "pedestrian_scenarios": "pedestrians crossing streets and sidewalk interactions",
            "parking_maneuvers": "parking lot driving and maneuvering scenarios"
        }

        uniqueness_results = []
        total_scenes_analyzed = 0
        total_unique_scenes = 0

        paginator = s3.get_paginator('list_objects_v2')
        actual_scene_dirs = []
        for page in paginator.paginate(Bucket=BUCKET, Prefix="pipeline-results/", Delimiter='/'):
            for prefix in page.get('CommonPrefixes', []):
                scene_dir = prefix['Prefix'].rstrip('/').split('/')[-1]
                if scene_dir.startswith('scene-'):
                    actual_scene_dirs.append(scene_dir)

        actual_total_scenes = len(actual_scene_dirs)
        pipeline_scene_set = set(actual_scene_dirs)

        for category_name, concept_desc in discovery_concepts.items():
            try:
                uniqueness_data = analyze_uniqueness_within_category(concept_desc, 0.35, pipeline_scene_set)

                if uniqueness_data.get("total_scenes", 0) > 0:
                    uniqueness_results.append({
                        "category": category_name,
                        "description": concept_desc,
                        "total_scenes": uniqueness_data["total_scenes"],
                        "estimated_unique_scenes": uniqueness_data.get("estimated_unique_scenes", 0),
                        "uniqueness_score": uniqueness_data.get("uniqueness_score", 0.0),
                        "redundancy_ratio": uniqueness_data.get("redundancy_ratio", 0.0),
                        "uniqueness_quality": uniqueness_data.get("uniqueness_quality", "unknown"),
                        "dto_value_estimate": uniqueness_data.get("dto_value_estimate", 0),
                        "similarity_distribution": uniqueness_data.get("similarity_distribution", {
                            "high_similarity_count": 0,
                            "medium_similarity_count": 0,
                            "low_similarity_count": 0
                        })
                    })
                    total_scenes_analyzed += uniqueness_data["total_scenes"]
                    total_unique_scenes += uniqueness_data.get("estimated_unique_scenes", 0)
            except Exception as e:
                logger.warning(f"Legacy uniqueness analysis failed for {category_name}: {e}")

        uniqueness_results.sort(key=lambda x: x["dto_value_estimate"], reverse=True)

        if total_scenes_analyzed > 0:
            scaling_factor = actual_total_scenes / total_scenes_analyzed
            scaled_total_unique_scenes = total_unique_scenes * scaling_factor
        else:
            scaled_total_unique_scenes = total_unique_scenes

        overall_uniqueness_ratio = scaled_total_unique_scenes / actual_total_scenes if actual_total_scenes > 0 else 0.0
        naive_dto_cost = actual_total_scenes * 30
        intelligent_dto_cost = scaled_total_unique_scenes * 30
        estimated_savings = naive_dto_cost - intelligent_dto_cost

        return {
            "analysis_method": "legacy_vector_similarity_uniqueness_analysis",
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "total_categories_analyzed": len(uniqueness_results),
            "total_scenes_analyzed": int(actual_total_scenes),
            "total_unique_scenes_estimated": round(scaled_total_unique_scenes, 1),
            "overall_uniqueness_ratio": round(overall_uniqueness_ratio, 3),
            "overall_redundancy_ratio": round(1.0 - overall_uniqueness_ratio, 3),
            "dto_cost_per_scene": 30,
            "dto_savings_estimate": {
                "naive_cost_usd": int(naive_dto_cost),
                "intelligent_cost_usd": int(intelligent_dto_cost),
                "estimated_savings_usd": int(estimated_savings),
                "efficiency_gain_percent": round((estimated_savings / naive_dto_cost * 100), 1) if naive_dto_cost > 0 else 0.0
            },
            "uniqueness_results": uniqueness_results,
            "analysis_quality": "high" if overall_uniqueness_ratio > 0.6 else "medium" if overall_uniqueness_ratio > 0.4 else "low"
        }

    except Exception as e:
        logger.error(f"Legacy ODD uniqueness analysis failed: {e}")
        return {"error": str(e), "uniqueness_results": []}


@router.get("/incremental-odd-updates")
def get_incremental_odd_updates(recent_scenes_limit: int = 10):
    """Incremental ODD updates for recent scenes"""
    return {"updates": [], "recent_scenes_analyzed": 0}


@router.get("/scenario-distribution-analysis")
def get_scenario_distribution_analysis():
    """Scenario distribution analysis"""
    return {"distribution": [], "total_scenarios": 0}


@router.get("/dynamic-thresholds")
def get_dynamic_thresholds():
    """Dynamic threshold configuration"""
    return {"thresholds": {"similarity": 0.35, "anomaly_severity": 0.6, "risk_score": 0.5}}


@router.get("/odd-discovery-alerts")
def get_odd_discovery_alerts():
    """ODD Discovery alerts"""
    return {"alerts": [], "total_alerts": 0}


@router.post("/rediscover")
async def trigger_odd_rediscovery():
    """Trigger async ODD category rediscovery using HDBSCAN clustering."""
    try:
        from discovery_status_manager import discovery_status_manager
        from services.dynamic_progress_tracker import DynamicProgressTracker
        from services.embedding_retrieval import load_all_embeddings

        job_id = discovery_status_manager.start_discovery_job()

        def run_discovery_background(job_id: str):
            try:
                progress_tracker = DynamicProgressTracker(job_id, discovery_status_manager)

                progress_tracker.start_phase('loading', "Loading scene embeddings from S3 storage")
                embeddings_data = load_all_embeddings()
                total_scenes = len(embeddings_data)
                progress_tracker.complete_phase()

                if total_scenes == 0:
                    discovery_status_manager.fail_discovery_job(job_id, "No scene embeddings found")
                    return

                progress_tracker.start_phase('clustering', f"Clustering {total_scenes} scenes")
                clustering_result = discover_odd_categories(min_cluster_size=5, embeddings_data=embeddings_data)

                if isinstance(clustering_result, dict) and "error" in clustering_result:
                    discovery_status_manager.fail_discovery_job(job_id, clustering_result["error"])
                    return

                if not clustering_result:
                    discovery_status_manager.fail_discovery_job(job_id, f"No clusters found in {total_scenes} scenes")
                    return

                progress_tracker.complete_phase()

                progress_tracker.start_phase('naming', f"Naming {len(clustering_result)} categories")
                named_clusters = name_discovered_clusters(clustering_result)
                progress_tracker.complete_phase()

                uniqueness_results = []
                total_unique = 0
                for cluster in named_clusters:
                    safety_result = calculate_safety_weighted_target(cluster)
                    total_scenes_cluster = cluster.scene_count
                    high_sim = int(total_scenes_cluster * (1 - cluster.uniqueness_score) * 0.6)
                    med_sim = int(total_scenes_cluster * (1 - cluster.uniqueness_score) * 0.4)
                    low_sim = total_scenes_cluster - high_sim - med_sim
                    
                    rep_scene_id = None
                    if hasattr(cluster, 'scenes') and cluster.scenes:
                        rep_scene_id = cluster.scenes[0].scene_id
                    
                    uniqueness_results.append({
                        "category": cluster.category_name,
                        "description": getattr(cluster, 'description', f"Discovered category with {total_scenes_cluster} scenes"),
                        "total_scenes": total_scenes_cluster,
                        "estimated_unique_scenes": safety_result["test_target"],
                        "uniqueness_score": cluster.uniqueness_score,
                        "redundancy_ratio": 1.0 - cluster.uniqueness_score,
                        "uniqueness_quality": "good" if cluster.uniqueness_score >= 0.6 else "moderate",
                        "dto_value_estimate": safety_result["dto_value"],
                        "representative_scene_id": rep_scene_id,
                        "similarity_distribution": {
                            "high_similarity_count": high_sim,
                            "medium_similarity_count": med_sim,
                            "low_similarity_count": max(0, low_sim)
                        }
                    })
                    total_unique += safety_result["test_target"]

                discovery_status_manager.complete_discovery_job(job_id, {
                    "uniqueness_results": uniqueness_results,
                    "total_categories_analyzed": len(uniqueness_results),
                    "total_scenes_analyzed": total_scenes,
                    "total_unique_scenes_estimated": total_unique,
                    "overall_uniqueness_ratio": total_unique / total_scenes if total_scenes > 0 else 0,
                    "dto_savings_estimate": {
                        "naive_cost_usd": total_scenes * 30,
                        "intelligent_cost_usd": total_unique * 30,
                        "estimated_savings_usd": (total_scenes - total_unique) * 30
                    }
                })

            except Exception as e:
                logger.error(f"Discovery failed: {e}")
                discovery_status_manager.fail_discovery_job(job_id, str(e))

        thread = threading.Thread(target=run_discovery_background, args=(job_id,), daemon=True)
        thread.start()

        return {"job_id": job_id, "status": "running", "message": "ODD rediscovery started"}

    except ImportError as e:
        logger.error(f"Discovery services not available: {e}")
        return {"job_id": "error", "status": "error", "message": f"Discovery services unavailable: {e}"}
    except Exception as e:
        logger.error(f"Failed to start discovery: {e}")
        return {"job_id": "error", "status": "error", "message": str(e)}


@router.get("/rediscover/{job_id}/status")
async def get_rediscovery_status(job_id: str):
    """Get rediscovery job status"""
    try:
        from discovery_status_manager import discovery_status_manager
        status = discovery_status_manager.get_job_status(job_id)
        if status:
            return status
        return {"job_id": job_id, "status": "not_found", "error_message": "Job not found"}
    except ImportError:
        return {"job_id": job_id, "status": "error", "error_message": "Status manager unavailable"}


@router.get("/rediscover/jobs")
async def list_discovery_jobs(limit: int = 10):
    """List recent discovery jobs"""
    try:
        from discovery_status_manager import discovery_status_manager
        jobs = discovery_status_manager.list_jobs(limit=limit)
        return {"jobs": jobs, "total": len(jobs)}
    except ImportError:
        return {"jobs": [], "total": 0}


@router.get("/coverage-matrix")
def get_coverage_matrix():
    """Hybrid ODD coverage matrix combining industry standards with discovered categories."""
    try:
        # Get scene count
        paginator = s3.get_paginator('list_objects_v2')
        scene_dirs = []
        for page in paginator.paginate(Bucket=BUCKET, Prefix='pipeline-results/', Delimiter='/'):
            for prefix in page.get('CommonPrefixes', []):
                scene_dir = prefix['Prefix'].rstrip('/').split('/')[-1]
                if scene_dir.startswith('scene-'):
                    scene_dirs.append(scene_dir)
        total_scenes = len(scene_dirs)

        def calculate_industry_target(total_scenes: int, risk_level: str, regulatory_importance: str) -> int:
            base_sample_size = max(30, int(total_scenes * 0.02))
            risk_multipliers = {"critical": 3.0, "high": 2.0, "medium": 1.2, "low": 0.8}
            regulatory_multipliers = {"critical": 1.5, "high": 1.2, "medium": 1.0, "low": 0.9}
            calculated = int(base_sample_size * risk_multipliers.get(risk_level, 1.0) * regulatory_multipliers.get(regulatory_importance, 1.0))
            return max(10, min(calculated, int(total_scenes * 0.30)))

        industry_categories = [
            {"category": "Highway Merging Scenarios", "type": "industry_standard", "current": 0,
             "target": calculate_industry_target(total_scenes, "medium", "high"),
             "estimated_coverage": calculate_industry_target(total_scenes, "medium", "high"),
             "risk_level": "medium", "hil_priority": "high", "description": "Complex lane changes and highway on-ramp scenarios"},
            {"category": "Urban Intersection Navigation", "type": "industry_standard", "current": 0,
             "target": calculate_industry_target(total_scenes, "high", "critical"),
             "estimated_coverage": calculate_industry_target(total_scenes, "high", "critical"),
             "risk_level": "high", "hil_priority": "critical", "description": "Traffic light intersections and pedestrian crossings"},
            {"category": "Adverse Weather Conditions", "type": "industry_standard", "current": 0,
             "target": calculate_industry_target(total_scenes, "high", "high"),
             "estimated_coverage": calculate_industry_target(total_scenes, "high", "high"),
             "risk_level": "high", "hil_priority": "high", "description": "Rain, snow, fog, and reduced visibility scenarios"},
            {"category": "Construction Zone Navigation", "type": "industry_standard", "current": 0,
             "target": calculate_industry_target(total_scenes, "medium", "medium"),
             "estimated_coverage": calculate_industry_target(total_scenes, "medium", "medium"),
             "risk_level": "medium", "hil_priority": "medium", "description": "Temporary lane changes and construction obstacles"},
            {"category": "Parking Lot Maneuvering", "type": "industry_standard", "current": 0,
             "target": calculate_industry_target(total_scenes, "low", "low"),
             "estimated_coverage": calculate_industry_target(total_scenes, "low", "low"),
             "risk_level": "low", "hil_priority": "low", "description": "Low-speed parking and tight maneuvering scenarios"},
            {"category": "Emergency Vehicle Response", "type": "industry_standard", "current": 0,
             "target": calculate_industry_target(total_scenes, "critical", "critical"),
             "estimated_coverage": calculate_industry_target(total_scenes, "critical", "critical"),
             "risk_level": "critical", "hil_priority": "critical", "description": "Response to ambulances, fire trucks, and police vehicles"}
        ]

        # Count scenes for each category
        for cat in industry_categories:
            try:
                query = f"autonomous vehicle driving scenario: {cat['description']}"
                vector = generate_embedding(query, DEFAULT_ANALYTICS_ENGINE)
                if vector:
                    results = s3vectors.query_vectors(
                        vectorBucketName=VECTOR_BUCKET,
                        indexName=INDICES_CONFIG[DEFAULT_ANALYTICS_ENGINE]["name"],
                        queryVector={"float32": vector},
                        topK=100, returnMetadata=True, returnDistance=True
                    )
                    unique_scenes = set()
                    for r in results.get("vectors", []):
                        if 1.0 - r.get("distance", 1.0) >= 0.35:
                            sid = r.get("metadata", {}).get("scene_id")
                            if sid and sid.startswith('scene-'):
                                unique_scenes.add(sid)
                    cat["current"] = len(unique_scenes)
            except Exception as e:
                logger.warning(f"Scene count failed for {cat['category']}: {e}")

        # Get discovered categories from cache
        discovered_categories = []
        try:
            from discovery_status_manager import discovery_status_manager
            for job in discovery_status_manager.list_jobs(limit=5):
                if job.get("status") == "completed" and job.get("discovered_categories", {}).get("uniqueness_results"):
                    for cat_data in job["discovered_categories"]["uniqueness_results"]:
                        actual = cat_data["total_scenes"]
                        target = cat_data.get("estimated_unique_scenes", actual)
                        discovered_categories.append({
                            "category": cat_data["category"],
                            "type": "discovered",
                            "actual_scenes": actual,
                            "risk_adaptive_target": round(target) if target else actual,
                            "average_risk_score": cat_data.get("average_risk_score"),
                            "uniqueness_score": cat_data["uniqueness_score"],
                            "discovery_method": "hdbscan_clustering",
                            "hil_priority": "high" if cat_data.get("uniqueness_quality") == "excellent" else "medium",
                            "description": cat_data.get("description", f"Data-driven cluster with {cat_data.get('uniqueness_quality', 'unknown')} uniqueness"),
                            "representative_scene_id": cat_data.get("representative_scene_id")
                        })
                    break
        except:
            pass

        # Compute average coverage % across categories (current/target per category)
        industry_pcts = [
            min((cat["current"] / cat["target"] * 100), 100)
            for cat in industry_categories if cat.get("target", 0) > 0
        ]
        industry_avg_pct = round(sum(industry_pcts) / len(industry_pcts), 1) if industry_pcts else 0

        discovered_pcts = [
            min((cat["actual_scenes"] / cat["risk_adaptive_target"] * 100), 100)
            for cat in discovered_categories if cat.get("risk_adaptive_target", 0) > 0
        ]
        discovered_avg_pct = round(sum(discovered_pcts) / len(discovered_pcts), 1) if discovered_pcts else 0

        return {
            "coverage_matrix": {
                "industry_standard_categories": industry_categories,
                "discovered_categories": discovered_categories,
                "coverage_analysis": {
                    "total_scenes_analyzed": total_scenes,
                    "industry_approach": {
                        "categories": len(industry_categories),
                        "coverage_percentage": industry_avg_pct
                    },
                    "discovered_approach": {
                        "categories": len(discovered_categories),
                        "coverage_percentage": discovered_avg_pct
                    }
                }
            },
            "metadata": {"analysis_type": "hybrid_odd_coverage", "generated_at": datetime.utcnow().isoformat()}
        }
    except Exception as e:
        logger.error(f"Coverage matrix failed: {e}")
        return {"coverage_matrix": {"industry_standard_categories": [], "discovered_categories": [], "coverage_analysis": {}}}
