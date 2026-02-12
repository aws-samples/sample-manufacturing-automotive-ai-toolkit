"""Stats routes - overview, trends, traffic light."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Response

from dependencies import s3, BUCKET
from services.cache_service import S3BackedMetricsCache
from services.scene_service import safe_parse_agent_analysis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stats"])

metrics_cache = S3BackedMetricsCache()


@router.get("/stats/overview")
def get_stats_overview():
    """Fleet Statistics from Phase 6 Pipeline Results"""
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET, Prefix="pipeline-results/", Delimiter='/')

        scene_dirs = []
        for s3_page in pages:
            for prefix in s3_page.get('CommonPrefixes', []):
                scene_dir = prefix['Prefix'].rstrip('/').split('/')[-1]
                if scene_dir.startswith('scene-') or scene_dir.isdigit():
                    scene_dirs.append(scene_dir)

        total_scenes = len(scene_dirs)

        def count_scene_anomaly(scene_dir):
            try:
                key = f"pipeline-results/{scene_dir}/agent-anomaly_detection-results.json"
                data = json.loads(s3.get_object(Bucket=BUCKET, Key=key)['Body'].read())
                anomaly_analysis = safe_parse_agent_analysis(data)
                severity = anomaly_analysis.get("anomaly_findings", {}).get("anomaly_severity", 0.0)
                return 1 if severity > 0.0 else 0
            except:
                return 0

        anomaly_count = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(count_scene_anomaly, sd): sd for sd in scene_dirs}
            for future in as_completed(futures):
                anomaly_count += future.result()

        try:
            cached = metrics_cache.get_metrics()
            if cached["source"] != "default":
                estimated_dto_savings = cached["estimated_savings_usd"]
                efficiency_ratio = cached["efficiency_gain_percent"] / 100.0
            else:
                efficiency_ratio = 0.276
                estimated_dto_savings = int(total_scenes * 30 * efficiency_ratio)
        except:
            efficiency_ratio = 0.276
            estimated_dto_savings = int(total_scenes * 8)

        response_data = {
            "scenarios_processed": total_scenes,
            "dto_savings_usd": estimated_dto_savings,
            "dto_efficiency_percent": round(efficiency_ratio * 100, 1),
            "anomalies_detected": anomaly_count,
            "status": "active"
        }

        return Response(
            content=json.dumps(response_data),
            media_type="application/json",
            headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=60"}
        )
    except Exception as e:
        logger.error(f"Error in get_stats_overview: {e}")
        return {"scenarios_processed": 0, "dto_savings_usd": 0, "dto_efficiency_percent": 0.0, "anomalies_detected": 0, "status": "error"}


@router.get("/stats/trends")
def get_analytics_trends():
    """Aggregates risk and anomaly data for charts from real scene data"""
    try:
        from routes.fleet import get_fleet_overview
        scenes_response = get_fleet_overview(limit=10000)

        if not scenes_response or not scenes_response.get("scenes"):
            return {"risk_timeline": [], "anomalies_by_type": {}, "total_scenes_analyzed": 0}

        scenes = scenes_response["scenes"]

        # Anomaly distribution by type
        anomaly_counts = {"Behavioral": 0, "Environmental": 0, "Traffic": 0, "Unknown": 0}

        # Risk timeline - per scene with real timestamps
        risk_over_time = []

        for scene in scenes:
            s = scene if isinstance(scene, dict) else scene.__dict__
            anomaly_status = s.get("anomaly_status", "NORMAL")
            tags = [tag.lower() for tag in s.get("tags", [])]

            # Categorize anomalies
            if anomaly_status in ["CRITICAL", "DEVIATION"]:
                if any(tag in tags for tag in ["construction", "weather", "night"]):
                    anomaly_counts["Environmental"] += 1
                elif any(tag in tags for tag in ["pedestrian", "vehicle", "intersection"]):
                    anomaly_counts["Traffic"] += 1
                elif any(tag in tags for tag in ["lane", "speed", "following"]):
                    anomaly_counts["Behavioral"] += 1
                else:
                    anomaly_counts["Unknown"] += 1

            # Risk timeline entry with real timestamp
            timestamp = s.get("timestamp", "")
            risk_over_time.append({
                "date": timestamp.split('T')[0] if timestamp else "unknown",
                "risk_score": s.get("risk_score", 0),
                "scene_id": s.get("scene_id", "")
            })

        total_scenes = len(scenes)

        response_data = {
            "anomalies_by_type": anomaly_counts,
            "risk_timeline": risk_over_time,
            "total_scenes_analyzed": total_scenes
        }

        return Response(
            content=json.dumps(response_data),
            media_type="application/json",
            headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=60"}
        )
    except Exception as e:
        logger.error(f"Error in get_analytics_trends: {e}")
        return {
            "anomalies_by_type": {"Behavioral": 0, "Environmental": 0, "Traffic": 0, "Unknown": 0},
            "risk_timeline": [],
            "total_scenes_analyzed": 0
        }


@router.get("/stats/traffic-light")
def get_traffic_light_stats():
    """Traffic light status summary - counts scenes by anomaly_status"""
    try:
        from routes.fleet import get_fleet_overview
        scenes_response = get_fleet_overview(limit=10000)
        scenes = scenes_response.get("scenes", [])

        counts = {"CRITICAL": 0, "DEVIATION": 0, "NORMAL": 0}
        for scene in scenes:
            status = scene.get("anomaly_status", "NORMAL") if isinstance(scene, dict) else getattr(scene, "anomaly_status", "NORMAL")
            if status in counts:
                counts[status] += 1

        total = len(scenes)
        return {
            "total_scenes": total,
            "critical": {
                "count": counts["CRITICAL"],
                "percentage": round(counts["CRITICAL"] / total * 100, 1) if total > 0 else 0
            },
            "deviation": {
                "count": counts["DEVIATION"],
                "percentage": round(counts["DEVIATION"] / total * 100, 1) if total > 0 else 0
            },
            "normal": {
                "count": counts["NORMAL"],
                "percentage": round(counts["NORMAL"] / total * 100, 1) if total > 0 else 0
            }
        }
    except Exception as e:
        logger.error(f"Error in get_traffic_light_stats: {e}")
        return {"total_scenes": 0, "critical": {"count": 0, "percentage": 0}, "deviation": {"count": 0, "percentage": 0}, "normal": {"count": 0, "percentage": 0}}
