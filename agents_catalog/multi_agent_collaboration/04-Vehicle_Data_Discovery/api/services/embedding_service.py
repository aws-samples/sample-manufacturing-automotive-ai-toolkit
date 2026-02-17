"""Embedding service for vector operations."""
import json
import logging
import boto3
from typing import List

logger = logging.getLogger(__name__)


def get_scene_behavioral_text(scene_id: str) -> str:
    """Fetch scene's behavioral description for auto-query generation."""
    from dependencies import s3, BUCKET
    
    try:
        bucket = BUCKET.replace("behavioral-vectors", "fleet-discovery-studio")
        
        # Try Phase 3 first
        try:
            key = f"processed/phase3/{scene_id}/internvideo25_analysis.json"
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(obj['Body'].read())
            desc = data.get("behavioral_analysis", {}).get("scene_understanding", {}).get("comprehensive_analysis", "")
            if desc and len(desc.strip()) > 20:
                return desc[:500]
        except Exception:
            pass

        # Fallback: Phase 6
        try:
            key = f"processed/phase6/{scene_id}/enhanced_orchestration_results.json"
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(obj['Body'].read())
            content = data.get("agent_results", {}).get("scene_understanding_worker", {}).get("scene_understanding", {}).get("analysis", {}).get("content", "")
            if content and len(content.strip()) > 20:
                return content[:500]
        except Exception:
            pass

        return f"driving scenarios similar to {scene_id}"
    except Exception as e:
        logger.error(f"Failed to fetch behavioral text for {scene_id}: {e}")
        return f"similar scenes to {scene_id}"


def generate_embedding(text: str, engine_type: str) -> List[float]:
    """Generate embedding vector using the correct engine."""
    from dependencies import INDICES_CONFIG, AWS_REGION

    config = INDICES_CONFIG.get(engine_type)
    if not config:
        return []

    try:
        if config["source"] == "bedrock":
            bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)
            response = bedrock.invoke_model(
                modelId=config["embedding_model"],
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"texts": [text], "input_type": "search_query", "truncate": "NONE"})
            )
            return json.loads(response['body'].read())['embeddings']['float'][0]

        elif config["source"] == "sagemaker":
            endpoint_name = config["embedding_model"]
            if not endpoint_name:
                return []
            sagemaker = boto3.client('sagemaker-runtime', region_name=AWS_REGION)
            response = sagemaker.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Body=json.dumps({"inputs": [text]})
            )
            result = json.loads(response['Body'].read())
            vector_array = json.loads(result[0])
            return vector_array[0]

    except Exception as e:
        logger.error(f"Embedding generation failed for {engine_type}: {e}")
        return []

    return []
