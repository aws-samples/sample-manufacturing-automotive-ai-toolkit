"""Scene routes - detail, video, thumbnail endpoints."""
import os
import json
import logging
import boto3
from botocore.config import Config
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from dependencies import s3, BUCKET
from services.scene_service import safe_parse_agent_analysis, extract_anomaly_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scene", tags=["scene"])


@router.get("/{scene_id}")
def get_scene_detail(scene_id: str):
    """The 'Forensic Lens' - Detailed Scene Inspector"""
    try:
        USE_CLOUDFRONT = os.getenv('USE_CLOUDFRONT_VIDEOS', 'false').lower() == 'true'
        
        def get_presigned_url(key):
            if USE_CLOUDFRONT:
                s3_accel = boto3.client('s3', region_name='us-west-2',
                    config=Config(s3={'use_accelerate_endpoint': True}))
                return s3_accel.generate_presigned_url('get_object',
                    Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=3600)
            return s3.generate_presigned_url('get_object',
                Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=3600)

        video_url = get_presigned_url(f"processed-videos/{scene_id}/CAM_FRONT.mp4")

        camera_urls = {}
        for cam in ["CAM_FRONT", "CAM_FRONT_LEFT", "CAM_FRONT_RIGHT", "CAM_BACK", "CAM_BACK_LEFT", "CAM_BACK_RIGHT"]:
            try:
                camera_urls[cam] = get_presigned_url(f"processed-videos/{scene_id}/{cam}.mp4")
            except:
                pass

        agents_data = {}
        for agent_type in ["scene_understanding", "anomaly_detection", "similarity_search"]:
            try:
                key = f"pipeline-results/{scene_id}/agent-{agent_type}-results.json"
                agents_data[agent_type] = json.loads(s3.get_object(Bucket=BUCKET, Key=key)['Body'].read())
            except:
                agents_data[agent_type] = {}

        phase3_data = {}
        try:
            p3_key = f"processed/phase3/{scene_id}/internvideo25_analysis.json"
            phase3_data = json.loads(s3.get_object(Bucket=BUCKET, Key=p3_key)['Body'].read())
        except:
            pass

        # Load Phase 6 output for properly formatted key_findings
        phase6_data = {}
        try:
            p6_key = f"processed/phase6/{scene_id}/enhanced_orchestration_results.json"
            phase6_data = json.loads(s3.get_object(Bucket=BUCKET, Key=p6_key)['Body'].read())
        except:
            pass

        scene_analysis = safe_parse_agent_analysis(agents_data.get("scene_understanding", {}))
        anomaly_analysis = safe_parse_agent_analysis(agents_data.get("anomaly_detection", {}))

        scene_analysis_data = scene_analysis.get("scene_analysis", {})
        scene_characteristics = scene_analysis.get("scene_characteristics", {})
        anomaly_findings = anomaly_analysis.get("anomaly_findings", {})
        anomaly_classification = anomaly_analysis.get("anomaly_classification", {})

        # Fix training_relevance if unavailable
        if scene_characteristics.get("training_relevance") == "Data unavailable":
            qm = phase3_data.get("behavioral_analysis", {}).get("quantified_metrics", {})
            risk = qm.get("risk_score", 0.0)
            safety = qm.get("safety_score", 0.0)
            if risk > 0.4 or safety < 0.6:
                scene_characteristics["training_relevance"] = f"High - Risk {risk:.2f}, safety {safety:.2f}"
            elif risk > 0.2 or safety < 0.8:
                scene_characteristics["training_relevance"] = f"Medium - Risk {risk:.2f}, safety {safety:.2f}"
            else:
                scene_characteristics["training_relevance"] = f"Low - Standard scenario"

        # Scene summary
        def get_scene_summary():
            vs = phase3_data.get("behavioral_analysis", {}).get("quantified_metrics", {}).get("visual_evidence_summary")
            if vs:
                return vs
            env = scene_analysis_data.get("environmental_conditions")
            if isinstance(env, dict):
                parts = [f"{k}: {v}" for k, v in env.items() if v and "unavailable" not in str(v).lower()]
                if parts:
                    return ". ".join(parts)
            elif env:
                return env
            return "Scene analysis pending"

        # Anomaly status
        severity = anomaly_findings.get("anomaly_severity", 0.0) if isinstance(anomaly_findings, dict) else 0.0
        try:
            severity = float(severity)
        except:
            severity = 0.0
        risk_score = phase3_data.get("behavioral_analysis", {}).get("quantified_metrics", {}).get("risk_score", 0.0)
        try:
            risk_score = float(risk_score)
        except:
            risk_score = 0.0

        if severity >= 0.6 or risk_score >= 0.5:
            anomaly_status = "CRITICAL"
        elif severity >= 0.2 and "low" not in str(anomaly_classification.get("hil_testing_value", "")).lower():
            anomaly_status = "DEVIATION"
        else:
            anomaly_status = "NORMAL"

        # Key findings - prefer Phase 6 formatted output
        key_findings = []
        p6_scene = phase6_data.get("agent_results", {}).get("scene_understanding_worker", {}).get("scene_understanding", {}).get("analysis", {})
        p6_kf = p6_scene.get("key_findings", [])
        if p6_kf:
            key_findings = [f for f in p6_kf if isinstance(f, str) and f.strip()]
        else:
            for f in scene_analysis.get("key_findings", []):
                if isinstance(f, str) and f.strip() and "unavailable" not in f.lower():
                    key_findings.append(f)

        # Behavioral insights
        behavioral_insights = []
        sc = scene_characteristics.get("safety_criticality", "").lower()
        if "high" in sc:
            behavioral_insights.append("High")
        elif "medium" in sc:
            behavioral_insights.append("Medium")
        elif "low" in sc:
            behavioral_insights.append("Low")
        mt = scene_analysis.get("recommendations", {}).get("model_training_focus", "")
        if isinstance(mt, list):
            mt = ", ".join(str(x) for x in mt)
        if mt and "unavailable" not in mt.lower():
            behavioral_insights.append(mt)

        phase6_parsed = {
            "scene_analysis_summary": get_scene_summary(),
            "key_findings": key_findings,
            "behavioral_insights": behavioral_insights,
            "environmental_context": scene_analysis_data.get("environmental_conditions", {}),
            "vehicle_performance_raw": scene_analysis_data.get("vehicle_behavior", {}),
            "scene_characteristics_raw": scene_characteristics,
            "recommendations_raw": scene_analysis.get("recommendations", {}),
            "anomaly_summary": extract_anomaly_summary(anomaly_findings),
            "anomaly_severity": severity,
            "confidence_score": scene_analysis.get("confidence_score", 0.0),
            "anomaly_status": anomaly_status,
            "anomaly_classification": {
                "anomaly_type": anomaly_classification.get("anomaly_type", ""),
                "hil_testing_value": anomaly_classification.get("hil_testing_value", ""),
                "investment_priority": anomaly_classification.get("investment_priority", ""),
                "training_gap_addressed": anomaly_classification.get("training_gap_addressed", "")
            },
            "recommendations": [scene_characteristics.get("training_relevance", "Analysis pending")]
        }

        return {
            "scene_id": scene_id,
            "primary_video_url": video_url,
            "all_camera_urls": camera_urls,
            "phase6_analysis": agents_data,
            "phase6_parsed": phase6_parsed,
            "phase3_raw_analysis": phase3_data.get("behavioral_analysis", {}),
            "intelligence_insights": {"training_value": scene_characteristics.get("training_relevance", "Analysis pending")},
            "metadata": {
                "processing_timestamp": agents_data.get("scene_understanding", {}).get("execution_timestamp", ""),
                "analysis_quality": "high" if agents_data.get("scene_understanding") else "partial"
            }
        }
    except Exception as e:
        logger.error(f"Error in get_scene_detail for {scene_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found") from e


@router.get("/{scene_id}/video")
def get_scene_video(scene_id: str):
    """Return primary video URL"""
    try:
        USE_CLOUDFRONT = os.getenv('USE_CLOUDFRONT_VIDEOS', 'false').lower() == 'true'
        if USE_CLOUDFRONT:
            s3_accel = boto3.client('s3', region_name='us-west-2',
                config=Config(s3={'use_accelerate_endpoint': True}))
            url = s3_accel.generate_presigned_url('get_object',
                Params={'Bucket': BUCKET, 'Key': f"processed-videos/{scene_id}/CAM_FRONT.mp4"}, ExpiresIn=3600)
        else:
            url = s3.generate_presigned_url('get_object',
                Params={'Bucket': BUCKET, 'Key': f"processed-videos/{scene_id}/CAM_FRONT.mp4"}, ExpiresIn=3600)
        return RedirectResponse(url=url)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Video not found for {scene_id}") from e


@router.get("/{scene_id}/thumbnail")
def get_scene_thumbnail(scene_id: str):
    """Return thumbnail (video placeholder)"""
    try:
        USE_CLOUDFRONT = os.getenv('USE_CLOUDFRONT_VIDEOS', 'false').lower() == 'true'
        if USE_CLOUDFRONT:
            s3_accel = boto3.client('s3', region_name='us-west-2',
                config=Config(s3={'use_accelerate_endpoint': True}))
            url = s3_accel.generate_presigned_url('get_object',
                Params={'Bucket': BUCKET, 'Key': f"processed-videos/{scene_id}/CAM_FRONT.mp4"}, ExpiresIn=3600)
        else:
            url = s3.generate_presigned_url('get_object',
                Params={'Bucket': BUCKET, 'Key': f"processed-videos/{scene_id}/CAM_FRONT.mp4"}, ExpiresIn=3600)
        return RedirectResponse(url=url)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thumbnail not found for {scene_id}") from e
