"""
Model configuration utility for quality inspection agents
"""
import boto3
import json

def get_model_id():
    """Get model ID with fallback logic"""
    try:
        ssm = boto3.client('ssm')
        # Try primary model
        primary_response = ssm.get_parameter(Name='/quality-inspection/primary-model/model-id')
        return primary_response['Parameter']['Value']
    except Exception:
        try:
            # Try secondary model
            secondary_response = ssm.get_parameter(Name='/quality-inspection/secondary-model/model-id')
            return secondary_response['Parameter']['Value']
        except Exception:
            # Fallback to hardcoded default
            return "amazon.nova-pro-v1:0"