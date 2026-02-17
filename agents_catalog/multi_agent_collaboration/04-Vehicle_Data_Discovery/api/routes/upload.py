"""Upload routes - authorization for file uploads."""
import logging
import uuid
from typing import Optional
from fastapi import APIRouter

from dependencies import get_s3, BUCKET

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])


@router.post("/upload/authorize")
def authorize_upload(filename: str, file_type: str, data_format: Optional[str] = "fleet_ros"):
    """Generate presigned URL for S3 upload and trigger pipeline"""
    try:
        s3 = get_s3()
        if not s3:
            return {"error": "S3 client not initialized"}
        
        upload_id = str(uuid.uuid4())[:8]
        s3_key = f"raw-data/fleet-pipeline/{upload_id}/{filename}"

        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': BUCKET, 'Key': s3_key, 'ContentType': file_type},
            ExpiresIn=3600
        )

        return {
            "upload_url": presigned_url,
            "upload_id": upload_id,
            "s3_key": s3_key,
            "expires_in": 3600,
            "pipeline_trigger": "automatic"
        }
    except Exception as e:
        logger.error(f"Upload authorization failed: {e}")
        return {"error": str(e)}
