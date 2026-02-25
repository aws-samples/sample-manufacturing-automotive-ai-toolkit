"""
sfc_cp_utils.s3 — S3 helpers for SFC Control Plane Lambda functions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)

_s3_client = None


def _client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


# ────────────────────────────────────────────────────────────────────────────
# Config JSON helpers
# ────────────────────────────────────────────────────────────────────────────

def get_config_json(bucket: str, s3_key: str) -> dict:
    """
    Fetch and JSON-parse an SFC config from S3.
    Raises botocore.exceptions.ClientError on missing key.
    """
    resp = _client().get_object(Bucket=bucket, Key=s3_key)
    body = resp["Body"].read()
    return json.loads(body)


def put_config_json(bucket: str, s3_key: str, config: dict) -> None:
    """Serialise *config* as JSON and write it to S3."""
    _client().put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=json.dumps(config, indent=2).encode(),
        ContentType="application/json",
    )


# ────────────────────────────────────────────────────────────────────────────
# Zip helpers
# ────────────────────────────────────────────────────────────────────────────

def put_zip(bucket: str, s3_key: str, zip_bytes: bytes) -> None:
    """Upload an in-memory zip to S3."""
    _client().put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=zip_bytes,
        ContentType="application/zip",
    )


# ────────────────────────────────────────────────────────────────────────────
# Certificate / asset helpers
# ────────────────────────────────────────────────────────────────────────────

def put_cert_asset(bucket: str, package_id: str, filename: str, content: str) -> str:
    """
    Write a certificate/key file to packages/{packageId}/assets/{filename}.
    Returns the S3 key.
    """
    key = f"packages/{package_id}/assets/{filename}"
    _client().put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode(),
        ContentType="text/plain",
    )
    return key


# ────────────────────────────────────────────────────────────────────────────
# Presigned URL helpers
# ────────────────────────────────────────────────────────────────────────────

def generate_presigned_url(bucket: str, s3_key: str, ttl_seconds: int = 300) -> str:
    """
    Generate a pre-signed GET URL for the given S3 object.
    Default TTL: 5 minutes (used for config-update control messages).
    """
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=ttl_seconds,
    )


def generate_presigned_download_url(bucket: str, s3_key: str, ttl_seconds: int = 3600) -> str:
    """
    Generate a 1-hour presigned GET URL for zip downloads.
    """
    return generate_presigned_url(bucket, s3_key, ttl_seconds=ttl_seconds)


# ────────────────────────────────────────────────────────────────────────────
# Key construction helpers
# ────────────────────────────────────────────────────────────────────────────

def config_s3_key(config_id: str, version: str) -> str:
    """Return the canonical S3 key for a versioned SFC config."""
    return f"configs/{config_id}/{version}/config.json"


def package_zip_s3_key(package_id: str) -> str:
    """Return the S3 key for a launch package zip."""
    return f"packages/{package_id}/launch-package.zip"