#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) file operations module.
Persists all files to S3 and indexes them in DynamoDB with base64-encoded content.
No local filesystem storage — all I/O goes to AWS.
"""

import os
import json
import csv
import base64
import logging
from typing import Tuple, Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# SSM parameter names for resource discovery (set by CDK stack)
_SSM_PARAM_S3_BUCKET = "/sfc-config-agent/s3-bucket-name"
_SSM_PARAM_DDB_TABLE = "/sfc-config-agent/ddb-table-name"

# Lazy-resolved resource names (populated on first access)
_resolved_s3_bucket: Optional[str] = None
_resolved_ddb_table: Optional[str] = None

# Lazy-initialized AWS clients
_s3_client = None
_ddb_table = None


def _get_ssm_parameter(param_name: str) -> Optional[str]:
    """Fetch a single SSM parameter value. Returns None on any error."""
    try:
        ssm = boto3.client("ssm")
        resp = ssm.get_parameter(Name=param_name)
        return resp["Parameter"]["Value"]
    except Exception as exc:
        logger.warning("Could not read SSM parameter %s: %s", param_name, exc)
        return None


def _resolve_s3_bucket() -> str:
    """Return the S3 bucket name, resolving from env var → SSM on first call."""
    global _resolved_s3_bucket
    if _resolved_s3_bucket is not None:
        return _resolved_s3_bucket

    # 1. Try environment variable (set explicitly or via .env)
    bucket = os.environ.get("SFC_S3_BUCKET_NAME", "")
    if bucket:
        _resolved_s3_bucket = bucket
        logger.info("SFC S3 bucket resolved from env var: %s", bucket)
        return _resolved_s3_bucket

    # 2. Fall back to SSM parameter (set by CDK stack)
    bucket = _get_ssm_parameter(_SSM_PARAM_S3_BUCKET)
    if bucket:
        _resolved_s3_bucket = bucket
        logger.info("SFC S3 bucket resolved from SSM (%s): %s", _SSM_PARAM_S3_BUCKET, bucket)
        return _resolved_s3_bucket

    # 3. Nothing found – return empty string (operations will fail gracefully)
    _resolved_s3_bucket = ""
    logger.error(
        "SFC S3 bucket name not available. "
        "Set SFC_S3_BUCKET_NAME env var or deploy the CDK stack to create SSM parameter %s",
        _SSM_PARAM_S3_BUCKET,
    )
    return _resolved_s3_bucket


def _resolve_ddb_table() -> str:
    """Return the DynamoDB table name, resolving from env var → SSM on first call."""
    global _resolved_ddb_table
    if _resolved_ddb_table is not None:
        return _resolved_ddb_table

    # 1. Try environment variable
    table = os.environ.get("SFC_DDB_TABLE_NAME", "")
    if table:
        _resolved_ddb_table = table
        logger.info("SFC DDB table resolved from env var: %s", table)
        return _resolved_ddb_table

    # 2. Fall back to SSM parameter
    table = _get_ssm_parameter(_SSM_PARAM_DDB_TABLE)
    if table:
        _resolved_ddb_table = table
        logger.info("SFC DDB table resolved from SSM (%s): %s", _SSM_PARAM_DDB_TABLE, table)
        return _resolved_ddb_table

    # 3. Default table name
    _resolved_ddb_table = "SFC_Agent_Files"
    logger.info("SFC DDB table using default: %s", _resolved_ddb_table)
    return _resolved_ddb_table




def _get_s3_client():
    """Get or create the S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _get_ddb_table():
    """Get or create the DynamoDB table resource."""
    global _ddb_table
    if _ddb_table is None:
        dynamodb = boto3.resource("dynamodb")
        _ddb_table = dynamodb.Table(_resolve_ddb_table())
    return _ddb_table


def _timestamp_prefix() -> str:
    """Generate an ISO timestamp prefix for S3 keys, safe for filenames.

    Returns:
        String like '2026-02-18T10-45-30Z'
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H-%M-%SZ")


def _hive_partition_prefix() -> str:
    """Generate a Hive-style date partition prefix for S3 keys.

    Returns:
        String like 'year=2026/month=02/day=18/hour=18'
    """
    now = datetime.now(timezone.utc)
    return now.strftime("year=%Y/month=%m/day=%d/hour=%H")


def _generate_presigned_url(s3_key: str, expiration: int = 3600) -> Optional[str]:
    """Generate a pre-signed URL for an S3 object.

    Args:
        s3_key: The S3 object key
        expiration: URL expiration time in seconds (default: 1 hour)

    Returns:
        Pre-signed URL string, or None if generation fails
    """
    bucket = _resolve_s3_bucket()
    if not bucket:
        logger.error("S3 bucket name not available – cannot generate pre-signed URL")
        return None
    try:
        url = _get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expiration,
        )
        logger.info(f"Generated pre-signed URL for s3://{bucket}/{s3_key}")
        return url
    except ClientError as e:
        logger.error(f"Failed to generate pre-signed URL for {s3_key}: {e}")
        return None


def _iso_timestamp() -> str:
    """Generate a full ISO timestamp for DynamoDB sort keys.

    Returns:
        String like '2026-02-18T10:45:30Z'
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _put_to_s3(s3_key: str, content: str, content_type: str = "text/plain") -> bool:
    """Upload content to S3.

    Args:
        s3_key: The S3 object key
        content: The text content to upload
        content_type: MIME type of the content

    Returns:
        True if successful, False otherwise
    """
    bucket = _resolve_s3_bucket()
    if not bucket:
        logger.error("S3 bucket name not available – cannot upload")
        return False
    try:
        _get_s3_client().put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )
        logger.info(f"Uploaded to S3: s3://{bucket}/{s3_key}")
        return True
    except ClientError as e:
        logger.error(f"S3 upload failed for {s3_key}: {e}")
        return False


def _put_to_ddb(
    file_type: str,
    s3_key: str,
    filename: str,
    content: str,
    content_type: str = "text/plain",
) -> bool:
    """Write file metadata and base64-encoded content to DynamoDB.

    Args:
        file_type: Category — 'config', 'result', 'conversation', or 'run'
        s3_key: The S3 object key
        filename: The original filename
        content: The text content (will be base64-encoded)
        content_type: MIME type

    Returns:
        True if successful, False otherwise
    """
    try:
        created_at = _iso_timestamp()
        sort_key = f"{created_at}#{s3_key}"
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        file_size = len(content.encode("utf-8"))

        item = {
            "file_type": file_type,
            "sort_key": sort_key,
            "filename": filename,
            "s3_key": s3_key,
            "created_at": created_at,
            "file_size": file_size,
            "content_type": content_type,
        }

        # DynamoDB item size limit is 400KB. Base64 overhead is ~33%.
        # Only store content_b64 if encoded size < 350KB to leave room for metadata.
        if len(content_b64) < 350_000:
            item["content_b64"] = content_b64
        else:
            logger.info(
                f"Content too large for DDB ({len(content_b64)} bytes b64), "
                f"storing metadata only. File available in S3: {s3_key}"
            )

        _get_ddb_table().put_item(Item=item)
        logger.info(f"Indexed in DDB: file_type={file_type}, sort_key={sort_key}")
        return True
    except ClientError as e:
        logger.error(f"DDB put_item failed for {filename}: {e}")
        return False


def _get_from_ddb(file_type: str, filename: str) -> Optional[str]:
    """Try to retrieve file content from DynamoDB by scanning for filename.

    Queries the file_type partition and looks for a matching filename.
    Returns the decoded content if found with content_b64, else None.

    Args:
        file_type: The file type partition ('config', 'result', etc.)
        filename: The filename to search for

    Returns:
        Decoded file content string, or None if not found
    """
    try:
        resp = _get_ddb_table().query(
            KeyConditionExpression="file_type = :ft",
            FilterExpression="filename = :fn",
            ExpressionAttributeValues={":ft": file_type, ":fn": filename},
            ScanIndexForward=False,  # newest first
            Limit=1,
        )
        items = resp.get("Items", [])
        if items and "content_b64" in items[0]:
            content_b64 = items[0]["content_b64"]
            return base64.b64decode(content_b64).decode("utf-8")
        return None
    except ClientError as e:
        logger.error(f"DDB query failed for {file_type}/{filename}: {e}")
        return None


def _get_from_s3(s3_key: str) -> Optional[str]:
    """Download and return text content from S3.

    Args:
        s3_key: The S3 object key

    Returns:
        File content as a string, or None if not found
    """
    bucket = _resolve_s3_bucket()
    if not bucket:
        return None
    try:
        resp = _get_s3_client().get_object(Bucket=bucket, Key=s3_key)
        return resp["Body"].read().decode("utf-8")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            logger.warning(f"S3 object not found: {s3_key}")
        else:
            logger.error(f"S3 get_object failed for {s3_key}: {e}")
        return None


def _find_s3_key_by_filename(prefix: str, filename: str) -> Optional[str]:
    """Find the most recent S3 key matching a filename under a prefix.

    S3 keys are timestamp-prefixed so we list and find the latest match.

    Args:
        prefix: S3 prefix to search under (e.g. 'configs/')
        filename: The filename to look for (suffix of the key)

    Returns:
        The full S3 key if found, or None
    """
    bucket = _resolve_s3_bucket()
    if not bucket:
        return None
    try:
        resp = _get_s3_client().list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
        )
        # Filter objects whose key ends with the filename (after the timestamp prefix)
        matching = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            key_filename = key.split("/")[-1]
            # Key format: prefix/2026-02-18T10-45-30Z_filename.json
            if key_filename.endswith(filename) or filename in key_filename:
                matching.append(obj)

        if matching:
            # Return the most recent (last by lexicographic S3 key order)
            matching.sort(key=lambda o: o["Key"], reverse=True)
            return matching[0]["Key"]
        return None
    except ClientError as e:
        logger.error(f"S3 list_objects_v2 failed for prefix={prefix}: {e}")
        return None


class SFCFileOperations:
    """Handles file I/O for SFC configurations using S3 and DynamoDB.

    All file storage is cloud-based — no local filesystem is used.
    Files are persisted to an S3 artifacts bucket (organized by prefix:
    configs/, results/, conversations/, runs/) and indexed in a DynamoDB
    metadata table with base64-encoded content for fast retrieval.
    """

    @staticmethod
    def read_config_from_file(filename: str) -> str:
        """Read an SFC configuration from cloud storage (DynamoDB index with S3 fallback).

        Checks DynamoDB first for fast cached retrieval, then falls back to
        scanning the S3 bucket under the configs/ prefix.

        Args:
            filename: Name of the config file to read (e.g. 'my-config.json')

        Returns:
            String result message with the loaded configuration or error details
        """
        try:
            # Normalize filename
            if not filename.lower().endswith(".json"):
                filename += ".json"

            basename = os.path.basename(filename)

            # Try DynamoDB first (fast path)
            content = _get_from_ddb("config", basename)
            if content:
                try:
                    config = json.loads(content)
                    config_json = json.dumps(config, indent=2)
                    return (
                        f"✅ Configuration loaded successfully from DynamoDB "
                        f"(file: '{basename}'):\n\n```json\n{config_json}\n```"
                    )
                except json.JSONDecodeError:
                    pass  # Fall through to S3

            # Fallback to S3
            s3_key = _find_s3_key_by_filename("configs/", basename)
            if s3_key:
                content = _get_from_s3(s3_key)
                if content:
                    try:
                        config = json.loads(content)
                        config_json = json.dumps(config, indent=2)
                        return (
                            f"✅ Configuration loaded successfully from S3 "
                            f"(key: '{s3_key}'):\n\n```json\n{config_json}\n```"
                        )
                    except json.JSONDecodeError:
                        return f"❌ Invalid JSON format in S3 object: '{s3_key}'"

            return f"❌ Configuration file not found: '{basename}'"

        except Exception as e:
            return f"❌ Error reading configuration: {str(e)}"

    @staticmethod
    def save_config_to_file(config_json: str, filename: str) -> str:
        """Save an SFC configuration to the S3 artifacts bucket and index it in DynamoDB.

        The file is stored under configs/year=YYYY/month=MM/day=DD/hour=HH/<filename>
        in S3, and a metadata entry (including base64-encoded content) is written to DynamoDB.
        A pre-signed download URL is returned as a markdown hyperlink.

        Args:
            config_json: SFC configuration JSON string to save
            filename: Name of the file to save the configuration to (e.g. 'my-config.json')

        Returns:
            String result message indicating success or failure, with a pre-signed download link
        """
        try:
            # Validate JSON
            config = json.loads(config_json)
            pretty_json = json.dumps(config, indent=2)

            # Normalize filename
            if not filename.lower().endswith(".json"):
                filename += ".json"
            basename = os.path.basename(filename)

            # Build Hive-partitioned S3 key
            partition = _hive_partition_prefix()
            s3_key = f"configs/{partition}/{basename}"

            # Upload to S3
            s3_ok = _put_to_s3(s3_key, pretty_json, content_type="application/json")

            # Index in DynamoDB
            ddb_ok = _put_to_ddb(
                file_type="config",
                s3_key=s3_key,
                filename=basename,
                content=pretty_json,
                content_type="application/json",
            )

            bucket = _resolve_s3_bucket()
            if s3_ok and ddb_ok:
                presigned_url = _generate_presigned_url(s3_key)
                download_link = (
                    f"[⬇ Download {basename}]({presigned_url})"
                    if presigned_url
                    else "(pre-signed URL generation failed)"
                )
                return (
                    f"✅ Configuration saved successfully:\n"
                    f"  • S3: `s3://{bucket}/{s3_key}`\n"
                    f"  • DynamoDB: {_resolve_ddb_table()} (config/{basename})\n"
                    f"  • {download_link}"
                )
            elif s3_ok:
                presigned_url = _generate_presigned_url(s3_key)
                download_link = (
                    f"[⬇ Download {basename}]({presigned_url})"
                    if presigned_url
                    else "(pre-signed URL generation failed)"
                )
                return (
                    f"⚠️ Configuration saved to S3 but DynamoDB indexing failed:\n"
                    f"  • S3: `s3://{bucket}/{s3_key}`\n"
                    f"  • {download_link}"
                )
            else:
                return f"❌ Failed to save configuration to S3 - {bucket}"

        except json.JSONDecodeError:
            return "❌ Invalid JSON configuration provided"
        except Exception as e:
            return f"❌ Error saving configuration: {str(e)}"

    @staticmethod
    def save_results_to_file(
        content: str, filename: str, current_config_name: str = None
    ) -> str:
        """Save content to the S3 artifacts bucket and index it in DynamoDB.

        The file is stored under results/year=YYYY/month=MM/day=DD/hour=HH/<filename>
        in S3. If a config run name is provided, an additional copy is stored under
        runs/<config_name>/year=YYYY/month=MM/day=DD/hour=HH/<filename>.
        A pre-signed download URL is returned as a markdown hyperlink.

        Args:
            content: Content to save
            filename: Name of the file (supports .txt, .vm, .md extensions)
            current_config_name: Current config run name (optional, creates a runs/ copy)

        Returns:
            String result message indicating success or failure, with a pre-signed download link
        """
        try:
            # Validate and normalize filename extension
            allowed_extensions = ["txt", "vm", "md"]
            has_extension = any(
                filename.lower().endswith(f".{ext}") for ext in allowed_extensions
            )
            if not has_extension:
                filename += ".txt"

            basename = os.path.basename(filename)

            # Determine content type
            ext = basename.rsplit(".", 1)[-1].lower()
            content_types = {
                "json": "application/json",
                "md": "text/markdown",
                "txt": "text/plain",
                "vm": "text/plain",
            }
            ct = content_types.get(ext, "text/plain")

            # Build Hive-partitioned S3 key
            partition = _hive_partition_prefix()
            s3_key = f"results/{partition}/{basename}"
            s3_ok = _put_to_s3(s3_key, content, content_type=ct)
            ddb_ok = _put_to_ddb(
                file_type="result",
                s3_key=s3_key,
                filename=basename,
                content=content,
                content_type=ct,
            )

            # Also save under runs/ if a config run name is provided
            run_s3_ok = False
            run_s3_key = None
            if current_config_name:
                run_s3_key = f"runs/{current_config_name}/{partition}/{basename}"
                run_s3_ok = _put_to_s3(run_s3_key, content, content_type=ct)
                if run_s3_ok:
                    _put_to_ddb(
                        file_type="run",
                        s3_key=run_s3_key,
                        filename=basename,
                        content=content,
                        content_type=ct,
                    )

            # Build result message
            bucket = _resolve_s3_bucket()
            if s3_ok and ddb_ok:
                presigned_url = _generate_presigned_url(s3_key)
                download_link = (
                    f"[⬇ Download {basename}]({presigned_url})"
                    if presigned_url
                    else "(pre-signed URL generation failed)"
                )
                msg = (
                    f"✅ Results saved successfully:\n"
                    f"  • S3: `s3://{bucket}/{s3_key}`\n"
                    f"  • DynamoDB: {_resolve_ddb_table()} (result/{basename})\n"
                    f"  • {download_link}"
                )
                if run_s3_ok and run_s3_key:
                    run_presigned_url = _generate_presigned_url(run_s3_key)
                    run_link = (
                        f"[⬇ Download run copy]({run_presigned_url})"
                        if run_presigned_url
                        else "(pre-signed URL generation failed)"
                    )
                    msg += f"\n  • Run copy: `s3://{bucket}/{run_s3_key}` — {run_link}"
                return msg
            elif s3_ok:
                presigned_url = _generate_presigned_url(s3_key)
                download_link = (
                    f"[⬇ Download {basename}]({presigned_url})"
                    if presigned_url
                    else "(pre-signed URL generation failed)"
                )
                return (
                    f"⚠️ Results saved to S3 but DynamoDB indexing failed:\n"
                    f"  • S3: `s3://{bucket}/{s3_key}`\n"
                    f"  • {download_link}"
                )
            else:
                return "❌ Failed to save results to S3"

        except Exception as e:
            return f"❌ Error saving results: {str(e)}"

    @staticmethod
    def read_context_from_file(file_path: str) -> Tuple[bool, str, Optional[str]]:
        """Read content from cloud storage (S3 and DynamoDB) to use as context.

        Searches across all S3 prefixes (configs/, results/, conversations/,
        runs/) and the DynamoDB metadata table. Supports JSON, Markdown, CSV,
        TXT, and VM files.

        Args:
            file_path: Filename or S3 key to read

        Returns:
            Tuple of (success, message, content)
        """
        try:
            basename = os.path.basename(file_path)
            ext = os.path.splitext(basename)[1].lower()

            # Supported text-based file extensions
            supported_extensions = [".json", ".md", ".csv", ".txt", ".vm"]

            if ext and ext not in supported_extensions:
                return (
                    False,
                    f"❌ Unsupported file type: '{ext}'. "
                    f"Supported types for cloud storage: {', '.join(supported_extensions)}",
                    None,
                )

            # Try to find the file in S3 across known prefixes
            content = None
            found_key = None

            for prefix in ["configs/", "results/", "conversations/", "runs/"]:
                s3_key = _find_s3_key_by_filename(prefix, basename)
                if s3_key:
                    content = _get_from_s3(s3_key)
                    found_key = s3_key
                    break

            # Also try the exact path as an S3 key
            if content is None:
                content = _get_from_s3(file_path)
                if content:
                    found_key = file_path

            # Try DynamoDB as a fallback
            if content is None:
                for file_type in ["config", "result", "conversation", "run"]:
                    content = _get_from_ddb(file_type, basename)
                    if content:
                        found_key = f"DynamoDB:{file_type}/{basename}"
                        break

            if content:
                file_size = len(content.encode("utf-8")) / 1024
                return (
                    True,
                    f"✅ Successfully read content from '{found_key}' ({file_size:.1f} KB)",
                    content,
                )
            else:
                return False, f"❌ File not found: '{file_path}'", None

        except Exception as e:
            return False, f"❌ Error reading file: {str(e)}", None