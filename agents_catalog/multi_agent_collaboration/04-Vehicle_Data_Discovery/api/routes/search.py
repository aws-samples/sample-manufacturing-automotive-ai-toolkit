"""Search routes - twin engine search."""
import json
import logging
from typing import List
from fastapi import APIRouter

from dependencies import s3, s3vectors, BUCKET, VECTOR_BUCKET, INDICES_CONFIG
from models.requests import SearchRequest
from utils.camera_utils import extract_scene_from_id, extract_camera_from_id
from services.embedding_service import generate_embedding, get_scene_behavioral_text

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


def cross_encoder_rerank_results(query_text: str, search_results: List[dict], source: str = None) -> List[dict]:
    """Cross-Encoder reranking for safety-critical scenarios."""
    if not query_text or not search_results:
        return search_results

    safety_keywords = {
        "critical": ["collision", "emergency", "brake", "swerve", "obstacle", "pedestrian", "cyclist"],
        "high": ["traffic", "intersection", "merge", "construction", "weather", "night", "rain"],
        "medium": ["parking", "lane", "turn", "signal", "slow", "stop", "yield"]
    }
    query_lower = query_text.lower()

    for result in search_results:
        safety_multiplier = 1.0
        scene_desc = str(result.get("metadata", "")).lower()

        critical = sum(1 for k in safety_keywords["critical"] if k in query_lower or k in scene_desc)
        high = sum(1 for k in safety_keywords["high"] if k in query_lower or k in scene_desc)
        medium = sum(1 for k in safety_keywords["medium"] if k in query_lower or k in scene_desc)

        if critical > 0:
            safety_multiplier = 1.5
        elif high > 0:
            safety_multiplier = 1.3
        elif medium > 0:
            safety_multiplier = 1.1

        if result.get("is_verified"):
            safety_multiplier *= 1.2
        if source == "odd_discovery":
            safety_multiplier *= 1.1

        result["rerank_score"] = min(1.0, result.get("score", 0.0) * safety_multiplier)
        result["safety_level"] = "critical" if critical else "high" if high else "medium" if medium else "standard"

    return sorted(search_results, key=lambda x: (x.get("is_verified", False), x.get("rerank_score", 0)), reverse=True)


@router.post("/search")
def twin_engine_search(request: SearchRequest):
    """Twin-Engine Search with Cross-Encoder Reranking."""
    results_map = {}
    query_text = request.query

    if request.scene_id and not query_text:
        query_text = get_scene_behavioral_text(request.scene_id)

    # Behavioral search
    if query_text:
        beh_vector = generate_embedding(query_text, "behavioral")
        if beh_vector:
            try:
                beh_results = s3vectors.query_vectors(
                    vectorBucketName=VECTOR_BUCKET,
                    indexName=INDICES_CONFIG["behavioral"]["name"],
                    queryVector={"float32": beh_vector},
                    topK=request.limit,
                    returnMetadata=True,
                    returnDistance=True
                )
                for res in beh_results.get("vectors", []):
                    sid = res["metadata"].get("scene_id")
                    score = 1.0 - res.get("distance", 1.0)
                    results_map[sid] = {
                        "scene_id": sid, "score": score, "engines": ["behavioral"],
                        "matches": ["Concept Match"], "metadata": res["metadata"], "is_verified": False
                    }
            except Exception as e:
                logger.error(f"Behavioral search failed: {e}")

    # Visual search
    vis_vector = None
    if request.scene_id:
        try:
            key = f"processed/phase4-5/{request.scene_id}/embeddings_output.json"
            bucket = BUCKET.replace("behavioral-vectors", "fleet-discovery-studio")
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(obj['Body'].read())
            vis_vector = data["multi_model_embeddings"]["cosmos"]["s3_records"][0]["data"]["float32"]
        except Exception as e:
            logger.error(f"Failed to load visual vector: {e}")
    elif request.query:
        vis_vector = generate_embedding(request.query, "visual")

    if vis_vector:
        try:
            vis_results = s3vectors.query_vectors(
                vectorBucketName=VECTOR_BUCKET,
                indexName=INDICES_CONFIG["visual"]["name"],
                queryVector={"float32": vis_vector},
                topK=request.limit,
                returnMetadata=True,
                returnDistance=True
            )
            for res in vis_results.get("vectors", []):
                sid = res["metadata"].get("scene_id", "unknown")
                camera_name = res["metadata"].get("camera_name", "CAM_FRONT")
                video_uri = res["metadata"].get("video_uri", "")

                if video_uri and "/" in video_uri:
                    fn = video_uri.split("/")[-1]
                    if fn.startswith("CAM_") and ".mp4" in fn:
                        camera_name = fn.replace(".mp4", "")

                if sid == "unknown":
                    camera_id = res.get("id", "")
                    if "_CAM_" in camera_id:
                        sid = extract_scene_from_id(camera_id)
                        camera_name = extract_camera_from_id(camera_id)

                if request.scene_id and sid == request.scene_id:
                    continue

                score = 1.0 - res.get("distance", 1.0)

                if sid in results_map:
                    existing = results_map[sid]
                    if "behavioral" in existing["engines"] and "visual" not in existing["engines"]:
                        existing["score"] += score * 0.5
                        existing["engines"].append("visual")
                        existing["matches"].append("Visual Match")
                        existing["is_verified"] = True
                    if "cameras" not in existing:
                        existing["cameras"] = []
                    existing["cameras"].append({"camera": camera_name, "score": score, "video_uri": video_uri})
                else:
                    results_map[sid] = {
                        "scene_id": sid, "score": score * 0.9, "engines": ["visual"],
                        "matches": ["Visual Pattern"], "metadata": res["metadata"], "is_verified": False,
                        "cameras": [{"camera": camera_name, "score": score, "video_uri": video_uri}]
                    }
        except Exception as e:
            logger.error(f"Visual search failed: {e}")

    final_results = sorted(results_map.values(), key=lambda x: (x.get("is_verified", False), x["score"]), reverse=True)

    search_context = {}
    if request.source:
        search_context["source"] = request.source
        if request.source == "odd_discovery" and request.uniqueness_score and request.uniqueness_score >= 0.8:
            for r in final_results:
                if r.get("is_verified"):
                    r["score"] = min(1.0, r["score"] * 1.1)
            final_results = sorted(final_results, key=lambda x: (x.get("is_verified", False), x["score"]), reverse=True)

    if request.source in ["coverage_matrix", "odd_discovery"] and query_text:
        final_results = cross_encoder_rerank_results(query_text, final_results[:50], request.source)
        search_context["reranking_applied"] = True

    engines_used = (["behavioral"] if query_text else []) + (["visual"] if vis_vector else [])
    verified_count = len([r for r in final_results if r.get("is_verified")])

    return {
        "query": query_text or request.scene_id,
        "results": final_results[:request.limit],
        "engines_active": engines_used,
        "search_metadata": {
            "total_results": len(final_results),
            "verified_count": verified_count,
            "search_type": "scene_similarity" if request.scene_id else "text_search",
            "auto_generated_query": bool(request.scene_id and not request.query),
            "search_context": search_context
        }
    }
