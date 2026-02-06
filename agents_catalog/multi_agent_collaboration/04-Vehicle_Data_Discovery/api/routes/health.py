"""Health and debug routes."""
import os
import boto3
from fastapi import APIRouter
from dependencies import s3, sfn, s3vectors, BUCKET, initialization_error

router = APIRouter(tags=["health"])


@router.get("/")
def root():
    """API Health Check"""
    return {"status": "fleet Discovery API Online", "version": "1.0.0"}


@router.get("/debug/s3")
def debug_s3_connectivity():
    """Diagnostic endpoint to debug S3 visibility issues"""
    results = {
        "1_identity": "unknown",
        "2_bucket_check": "unknown", 
        "3_prefix_check": "unknown",
        "4_raw_list": [],
        "initialization_error": initialization_error,
        "env_vars": {
            "bucket": BUCKET,
            "region": os.environ.get("AWS_DEFAULT_REGION", "not_set"),
            "aws_region": os.environ.get("AWS_REGION", "not_set"),
        },
        "client_status": {
            "s3_client": "initialized" if s3 is not None else "None",
            "sfn_client": "initialized" if sfn is not None else "None",
            "s3vectors_client": "initialized" if s3vectors is not None else "None",
        }
    }

    try:
        sts = boto3.client('sts', region_name='us-west-2')
        identity = sts.get_caller_identity()
        results["1_identity"] = {"arn": identity.get("Arn"), "account": identity.get("Account")}
    except Exception as e:
        results["1_identity"] = f"FAILED: {str(e)}"

    try:
        s3.head_bucket(Bucket=BUCKET)
        results["2_bucket_check"] = "ACCESSIBLE"
    except Exception as e:
        results["2_bucket_check"] = f"FAILED: {str(e)}"

    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix="pipeline-results/", Delimiter='/', MaxKeys=5)
        prefixes = [p.get('Prefix') for p in response.get('CommonPrefixes', [])]
        results["3_prefix_check"] = f"Found {len(prefixes)} prefixes"
        results["4_raw_list"] = prefixes
    except Exception as e:
        results["3_prefix_check"] = f"FAILED: {str(e)}"

    return results
