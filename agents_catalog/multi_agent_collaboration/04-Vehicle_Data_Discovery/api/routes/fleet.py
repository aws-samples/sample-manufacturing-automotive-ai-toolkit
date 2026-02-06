"""Fleet routes - overview and related endpoints."""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter

from dependencies import s3, BUCKET, fleet_overview_cache
from models.responses import SceneSummary
from services.scene_service import (
    safe_parse_agent_analysis, format_tags_for_ui, apply_metadata_filter
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/overview")
def get_fleet_overview(page: int = 1, limit: int = 50, filter: str = "all"):
    """The 'God View' - Read ONLY what the Agents decided"""
    cache_key = f"fleet_overview_{page}_{limit}_{filter}"
    current_time = time.time()

    if (cache_key in fleet_overview_cache and
        fleet_overview_cache[cache_key].get("data") is not None and
        current_time - fleet_overview_cache[cache_key].get("timestamp", 0) < 300):
        return fleet_overview_cache[cache_key]["data"]

    scenes = []
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET, Prefix="pipeline-results/", Delimiter='/')

        scene_dirs = []
        for s3_page in pages:
            for prefix in s3_page.get('CommonPrefixes', []):
                scene_dir = prefix['Prefix'].rstrip('/').split('/')[-1]
                if scene_dir.startswith('scene-'):
                    scene_dirs.append(scene_dir)

        def get_scene_number(scene_dir):
            try:
                return int(scene_dir.replace('scene-', ''))
            except ValueError:
                return 0

        all_scene_dirs = sorted(scene_dirs, key=get_scene_number, reverse=True)
        total_scenes = len(all_scene_dirs)

        if filter == "all":
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            scene_dirs = all_scene_dirs[start_idx:end_idx]
        else:
            scene_dirs = all_scene_dirs

        def process_scene(scene_id):
            scene_agents = {}
            try:
                p3_key = f"processed/phase3/{scene_id}/internvideo25_analysis.json"
                phase3_data = json.loads(s3.get_object(Bucket=BUCKET, Key=p3_key)['Body'].read())
                scene_agents['phase3'] = phase3_data.get("behavioral_analysis", {})
            except Exception:
                scene_agents['phase3'] = {}

            try:
                key = f"pipeline-results/{scene_id}/agent-scene_understanding-results.json"
                data = json.loads(s3.get_object(Bucket=BUCKET, Key=key)['Body'].read())
                scene_agents['scene_understanding'] = data
            except Exception:
                return None

            try:
                key = f"pipeline-results/{scene_id}/agent-anomaly_detection-results.json"
                data = json.loads(s3.get_object(Bucket=BUCKET, Key=key)['Body'].read())
                scene_agents['anomaly_detection'] = data
            except Exception:
                scene_agents['anomaly_detection'] = {}

            return scene_id, scene_agents

        scene_data = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_scene = {executor.submit(process_scene, sid): sid for sid in scene_dirs}
            for future in as_completed(future_to_scene):
                result = future.result()
                if result:
                    scene_id, agents = result
                    scene_data[scene_id] = agents

        for scene_id, agents in scene_data.items():
            if not scene_id.startswith('scene-'):
                continue

            scene_understanding = agents.get('scene_understanding', {})
            anomaly_detection = agents.get('anomaly_detection', {})
            phase3_data = agents.get('phase3', {})

            quantified_metrics = phase3_data.get('quantified_metrics', {})
            risk_score = quantified_metrics.get('risk_score', 0.0)
            confidence_score = quantified_metrics.get('confidence_score', 0.0)

            if not isinstance(risk_score, (int, float)):
                try:
                    risk_score = float(risk_score)
                except (ValueError, TypeError):
                    risk_score = 0.0

            if not isinstance(confidence_score, (int, float)):
                try:
                    confidence_score = float(confidence_score)
                except (ValueError, TypeError):
                    confidence_score = 0.0

            scene_analysis = safe_parse_agent_analysis(scene_understanding)
            anomaly_analysis = safe_parse_agent_analysis(anomaly_detection)

            anomaly_findings = anomaly_analysis.get("anomaly_findings", {})
            anomaly_classification = anomaly_analysis.get("anomaly_classification", {})

            # HIL Priority
            raw_priority = "LOW"
            if anomaly_classification.get("hil_testing_value"):
                agent_hil = str(anomaly_classification["hil_testing_value"]).lower().strip()
                if agent_hil.startswith("high"):
                    raw_priority = "HIGH"
                elif agent_hil.startswith("medium"):
                    raw_priority = "MEDIUM"
            hil_priority = raw_priority

            # Anomaly Status
            severity = anomaly_findings.get("anomaly_severity", 0.0) if isinstance(anomaly_findings, dict) else 0.0
            if not isinstance(severity, (int, float)):
                try:
                    severity = float(severity)
                except (ValueError, TypeError):
                    severity = 0.0

            if severity >= 0.6 or risk_score >= 0.5:
                anomaly_status = "CRITICAL"
            elif severity >= 0.2 and "low" not in str(anomaly_classification.get("hil_testing_value", "")).lower():
                anomaly_status = "DEVIATION"
            else:
                anomaly_status = "NORMAL"

            # Tags
            raw_tags = []
            scene_characteristics = scene_analysis.get("scene_characteristics", {})
            if scene_characteristics.get("scenario_type"):
                raw_tags.append(scene_characteristics["scenario_type"])
            if scene_characteristics.get("complexity_level"):
                raw_tags.append(scene_characteristics["complexity_level"])
            if not raw_tags:
                business_intel = quantified_metrics.get('business_intelligence', {})
                if business_intel.get('scenario_type'):
                    raw_tags.append(business_intel['scenario_type'])
            tags = format_tags_for_ui(raw_tags)

            # Description
            scene_analysis_data = scene_analysis.get("scene_analysis", {})
            description = scene_analysis_data.get("environmental_conditions", "Analysis complete")
            description = str(description) if description else "Analysis complete"

            hil_qualification = {
                "level": hil_priority,
                "anomaly_detected": anomaly_status in ["CRITICAL", "DEVIATION"],
                "reason": f"Agent classified as {hil_priority} priority"
            }

            try:
                scenes.append(SceneSummary(
                    scene_id=scene_id,
                    risk_score=risk_score,
                    anomaly_status=anomaly_status,
                    hil_priority=hil_priority,
                    description_preview=description,
                    tags=tags,
                    confidence_score=confidence_score,
                    timestamp=scene_understanding.get("execution_timestamp", ""),
                    hil_qualification=hil_qualification
                ))
            except Exception as e:
                logger.error(f"SceneSummary creation failed for {scene_id}: {e}")

        scenes.sort(key=lambda x: x.risk_score, reverse=True)
        filtered_scenes = apply_metadata_filter(scenes, filter)

        if filter == "all":
            paginated_scenes = filtered_scenes
            total_count = total_scenes
        else:
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_scenes = filtered_scenes[start_idx:end_idx]
            total_count = len(filtered_scenes)

        response_data = {
            "scenes": paginated_scenes,
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit
        }

        fleet_overview_cache[cache_key] = {"data": response_data, "timestamp": current_time}
        return response_data

    except Exception as e:
        logger.error(f"Error in get_fleet_overview: {e}")
        return {"scenes": [], "total_count": 0, "page": page, "limit": limit, "total_pages": 0}
