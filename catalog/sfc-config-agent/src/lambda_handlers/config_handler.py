"""
WP-04 — fn-configs Lambda handler.

Covers all config management endpoints:
  GET    /configs
  POST   /configs
  GET    /configs/focus
  DELETE /configs/focus
  POST   /configs/{configId}/focus
  GET    /configs/{configId}
  PUT    /configs/{configId}
  DELETE /configs/{configId}
  GET    /configs/{configId}/versions
  GET    /configs/{configId}/versions/{version}
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

from boto3.dynamodb.conditions import Key

from sfc_cp_utils import ddb as ddb_util
from sfc_cp_utils import s3 as s3_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Env vars injected by CDK
CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
CONFIG_TABLE_NAME = os.environ["CONFIG_TABLE_NAME"]
STATE_TABLE_NAME = os.environ["STATE_TABLE_NAME"]

_dynamodb = boto3.resource("dynamodb")
_config_table = _dynamodb.Table(CONFIG_TABLE_NAME)
_state_table = _dynamodb.Table(STATE_TABLE_NAME)

# The SFC_Agent_Files table uses PK=file_type / SK=sort_key.
# For configs we use:
#   file_type = "config"
#   sort_key  = "{configId}#{version}"
# This allows querying all versions of a configId with begins_with.
_FILE_TYPE_CONFIG = "config"

def _config_sort_key(config_id: str, version: str) -> str:
    return f"{config_id}#{version}"


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}

    logger.info("Request: %s %s", method, path)

    try:
        # Route dispatch
        if path == "/configs" and method == "GET":
            return _list_configs()

        if path == "/configs" and method == "POST":
            body = _parse_body(event)
            return _create_config(body)

        if path == "/configs/focus" and method == "GET":
            return _get_focus()

        if path == "/configs/focus" and method == "DELETE":
            return _clear_focus()

        if path.endswith("/focus") and method == "POST":
            config_id = path_params.get("configId")
            body = _parse_body(event)
            return _set_focus(config_id, body.get("version"))

        if "/versions/" in path and method == "GET":
            config_id = path_params.get("configId")
            version = path_params.get("version")
            return _get_config_version(config_id, version)

        if path.endswith("/versions") and method == "GET":
            config_id = path_params.get("configId")
            return _list_config_versions(config_id)

        config_id = path_params.get("configId")
        if config_id:
            if method == "GET":
                return _get_config(config_id)
            if method == "PUT":
                body = _parse_body(event)
                return _save_config(config_id, body)
            if method == "DELETE":
                return _delete_config(config_id)
            if method == "PATCH" and path.endswith("/tags"):
                return _update_config_tags(config_id, _parse_body(event))

        return _error(404, "NOT_FOUND", f"No route matched: {method} {path}")

    except Exception:  # noqa: BLE001
        logger.exception("Unhandled error")
        # Do not expose str(exc) — it may leak stack traces or implementation
        # details to the caller. Full error is captured in CloudWatch Logs above.
        return _error(500, "INTERNAL_ERROR", "An internal error occurred. Check CloudWatch logs for details.")


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

def _list_configs() -> dict:
    """Return one summary entry per configId (latest version only).
    The underlying table is SFC_Agent_Files (PK=file_type, SK=sort_key).
    We query by PK='config' to retrieve all config records, then
    de-duplicate to keep the newest version per configId.
    """
    resp = _config_table.query(
        KeyConditionExpression=Key("file_type").eq(_FILE_TYPE_CONFIG),
        ScanIndexForward=False,
    )
    all_items = resp.get("Items", [])
    # De-duplicate: keep the newest version per configId.
    # Skip items that lack configId — these are legacy agent base64-index records.
    # Skip soft-deleted configs entirely.
    latest: dict[str, dict] = {}
    for item in all_items:
        cid = item.get("configId")
        if not cid:
            continue
        if item.get("deleted"):
            continue
        existing = latest.get(cid)
        if existing is None or item.get("version", "") > existing.get("version", ""):
            latest[cid] = item
    configs = [_strip_content(_to_api(i)) for i in latest.values()]
    return _ok({"configs": configs})


def _get_focus() -> dict:
    state = ddb_util.get_control_state(_state_table)
    if not state:
        return _ok({"stateKey": "global", "focusedConfigId": None, "focusedConfigVersion": None})
    return _ok(state)


def _clear_focus() -> dict:
    """Clear the focused config — writes a state record with null focus fields."""
    _state_table.put_item(Item={
        "stateKey": "global",
        "focusedConfigId": None,
        "focusedConfigVersion": None,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })
    return _ok({"stateKey": "global", "focusedConfigId": None, "focusedConfigVersion": None})


def _set_focus(config_id: str | None, version: str | None) -> dict:
    if not config_id or not version:
        return _error(400, "BAD_REQUEST", "configId path param and version body field are required")
    # Validate the config/version exists
    item = _ddb_get_config(config_id, version)
    if not item:
        return _error(404, "NOT_FOUND", f"Config {config_id}/{version} not found")
    state = ddb_util.set_focused_config(_state_table, config_id, version)
    return _ok(state)


def _get_config(config_id: str) -> dict:
    item = _ddb_get_config(config_id)
    if not item:
        return _error(404, "NOT_FOUND", f"Config {config_id} not found")
    api_item = _to_api(item)
    s3_key = api_item.get("s3Key") or s3_util.config_s3_key(config_id, api_item["version"])
    try:
        content = s3_util.get_config_json(CONFIGS_BUCKET, s3_key)
    except Exception:
        content = None
    result = dict(api_item)
    result["content"] = content
    return _ok(result)


def _list_config_versions(config_id: str) -> dict:
    resp = _config_table.query(
        KeyConditionExpression=(
            Key("file_type").eq(_FILE_TYPE_CONFIG)
            & Key("sort_key").begins_with(f"{config_id}#")
        ),
        ScanIndexForward=False,
    )
    items = resp.get("Items", [])
    if not items:
        return _error(404, "NOT_FOUND", f"No versions found for configId {config_id}")
    return _ok({"versions": [_strip_content(_to_api(i)) for i in items]})


def _get_config_version(config_id: str, version: str) -> dict:
    item = _ddb_get_config(config_id, version)
    if not item:
        return _error(404, "NOT_FOUND", f"Config {config_id}/{version} not found")
    api_item = _to_api(item)
    s3_key = api_item.get("s3Key") or s3_util.config_s3_key(config_id, version)
    try:
        content = s3_util.get_config_json(CONFIGS_BUCKET, s3_key)
    except Exception:
        content = None
    result = dict(api_item)
    result["content"] = content
    return _ok(result)


def _create_config(body: dict) -> dict:
    """Create a new config with a freshly generated configId."""
    name = body.get("name", "").strip()
    if not name:
        return _error(400, "BAD_REQUEST", "Request body must include 'name'")

    raw_content = body.get("content", {})
    # Accept a JSON string (e.g. "{}") or a dict
    if isinstance(raw_content, str):
        try:
            raw_content = json.loads(raw_content)
        except json.JSONDecodeError:
            return _error(400, "BAD_REQUEST", "'content' must be a valid JSON object or JSON string")
    if not isinstance(raw_content, dict):
        return _error(400, "BAD_REQUEST", "'content' must be a JSON object")

    config_id = str(uuid.uuid4())
    return _save_config(config_id, {**body, "content": raw_content})


def _delete_config(config_id: str) -> dict:
    """Soft-delete all versions of a config by setting deleted=True in DDB.

    Refuses to delete a config that is currently in focus.
    No DDB items or S3 objects are physically removed.
    """
    # Guard: refuse to delete the focused config
    state = ddb_util.get_control_state(_state_table)
    if state and state.get("focusedConfigId") == config_id:
        return _error(
            409,
            "CONFLICT",
            f"Config {config_id} is currently in focus and cannot be deleted. "
            "Clear the focus first.",
        )

    # Query all versions for this configId
    resp = _config_table.query(
        KeyConditionExpression=(
            Key("file_type").eq(_FILE_TYPE_CONFIG)
            & Key("sort_key").begins_with(f"{config_id}#")
        ),
    )
    items = resp.get("Items", [])
    if not items:
        return _error(404, "NOT_FOUND", f"Config {config_id} not found")

    deleted_at = datetime.now(timezone.utc).isoformat()
    for item in items:
        _config_table.update_item(
            Key={
                "file_type": item["file_type"],
                "sort_key": item["sort_key"],
            },
            UpdateExpression="SET deleted = :t, deletedAt = :ts",
            ExpressionAttributeValues={":t": True, ":ts": deleted_at},
        )

    logger.info("Soft-deleted config %s (%d versions)", config_id, len(items))
    return _ok({"message": f"Config {config_id} deleted ({len(items)} version(s) marked)"})


def _update_config_tags(config_id: str, body: dict) -> dict:
    """PATCH /configs/{configId}/tags — update tags on the latest version."""
    item = _ddb_get_config(config_id)
    if not item:
        return _error(404, "NOT_FOUND", f"Config {config_id} not found")
    tags = body.get("tags", [])
    if not isinstance(tags, list):
        return _error(400, "BAD_REQUEST", "'tags' must be a list of strings")
    _config_table.update_item(
        Key={
            "file_type": item["file_type"],
            "sort_key": item["sort_key"],
        },
        UpdateExpression="SET tags = :t",
        ExpressionAttributeValues={":t": tags},
    )
    return _ok({"configId": config_id, "tags": tags})


def _save_config(config_id: str, body: dict) -> dict:
    content = body.get("content")
    if content is None:
        return _error(400, "BAD_REQUEST", "Request body must include 'content' (SFC config JSON)")
    if not isinstance(content, dict):
        return _error(400, "BAD_REQUEST", "'content' must be a JSON object")

    version = datetime.now(timezone.utc).isoformat()
    s3_key = s3_util.config_s3_key(config_id, version)

    # Write to S3
    s3_util.put_config_json(CONFIGS_BUCKET, s3_key, content)

    # Write metadata to DDB using the file_type/sort_key schema
    tags = body.get("tags")
    item = {
        "file_type": _FILE_TYPE_CONFIG,
        "sort_key": _config_sort_key(config_id, version),
        "configId": config_id,
        "version": version,
        "name": body.get("name", config_id),
        "description": body.get("description", ""),
        "s3Key": s3_key,
        "status": "active",
        "createdAt": version,
    }
    if isinstance(tags, list):
        item["tags"] = tags
    _config_table.put_item(Item=item)

    return _ok(_strip_content(_to_api(item)))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ddb_get_config(config_id: str, version: str | None = None) -> dict | None:
    """
    Fetch a config item from the SFC_Agent_Files table (PK=file_type, SK=sort_key).
    If *version* is None, returns the latest version for the given configId.
    """
    if version:
        resp = _config_table.get_item(
            Key={
                "file_type": _FILE_TYPE_CONFIG,
                "sort_key": _config_sort_key(config_id, version),
            }
        )
        return resp.get("Item")

    # Query all versions for this configId (sort_key begins_with configId#),
    # sorted descending so the first result is the latest.
    resp = _config_table.query(
        KeyConditionExpression=(
            Key("file_type").eq(_FILE_TYPE_CONFIG)
            & Key("sort_key").begins_with(f"{config_id}#")
        ),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def _to_api(item: dict) -> dict:
    """
    Strip internal DynamoDB key fields (file_type, sort_key) from a table item
    so the API response only contains the logical config fields.
    """
    return {k: v for k, v in item.items() if k not in ("file_type", "sort_key")}


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    return json.loads(raw)


def _strip_content(item: dict) -> dict:
    """Return item without the inline content field (keeps payload small)."""
    return {k: v for k, v in item.items() if k != "content"}


def _ok(body: dict, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _error(status: int, error: str, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": error, "message": message}),
    }