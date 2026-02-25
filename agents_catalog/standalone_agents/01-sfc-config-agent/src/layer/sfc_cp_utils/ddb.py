"""
sfc_cp_utils.ddb — DynamoDB helpers for SFC Control Plane Lambda functions.
All functions accept boto3 Table resources (not client) for conciseness.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Config helpers  (SfcConfigTable: PK=configId, SK=version)
# ────────────────────────────────────────────────────────────────────────────

def get_config(table, config_id: str, version: str | None = None) -> dict | None:
    """
    Return a config item from SfcConfigTable.
    If *version* is None, returns the latest version (highest SK value).
    Returns None when the item does not exist.
    """
    if version:
        resp = table.get_item(Key={"configId": config_id, "version": version})
        return resp.get("Item")

    # Query all versions, sort descending, take first
    resp = table.query(
        KeyConditionExpression=Key("configId").eq(config_id),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def list_configs(table) -> list[dict]:
    """
    Return all config items from SfcConfigTable.
    Callers should de-duplicate by configId to get latest-per-config if needed.
    """
    items: list[dict] = []
    kwargs: dict[str, Any] = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return items


def list_config_versions(table, config_id: str) -> list[dict]:
    """Return all version items for a given configId, newest first."""
    resp = table.query(
        KeyConditionExpression=Key("configId").eq(config_id),
        ScanIndexForward=False,
    )
    return resp.get("Items", [])


def put_config(table, item: dict) -> None:
    """Write a config item to SfcConfigTable (PK=configId, SK=version)."""
    table.put_item(Item=item)


def update_config_status(table, config_id: str, version: str, status: str) -> None:
    """Update the status field of a specific config version."""
    table.update_item(
        Key={"configId": config_id, "version": version},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )


# ────────────────────────────────────────────────────────────────────────────
# Launch Package helpers  (LaunchPackageTable: PK=packageId, SK=createdAt)
# ────────────────────────────────────────────────────────────────────────────

def get_package(table, package_id: str) -> dict | None:
    """
    Return the LaunchPackageTable item for *package_id*.
    Performs a Query (PK only) and returns the first result (there should be
    exactly one item per packageId since UUIDs are unique).
    Returns None when not found.
    """
    resp = table.query(
        KeyConditionExpression=Key("packageId").eq(package_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def list_packages(table) -> list[dict]:
    """Return all launch package items (full scan)."""
    items: list[dict] = []
    kwargs: dict[str, Any] = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return items


def put_package(table, item: dict) -> None:
    """Write a launch package item."""
    table.put_item(Item=item)


def update_package(table, package_id: str, created_at: str, attrs: dict) -> None:
    """
    Patch arbitrary attributes on a LaunchPackageTable item.
    *attrs* is a plain dict of attribute_name → new_value.
    Uses SET for all supplied keys.
    """
    if not attrs:
        return
    names: dict[str, str] = {}
    values: dict[str, Any] = {}
    set_parts: list[str] = []

    for i, (k, v) in enumerate(attrs.items()):
        placeholder_name = f"#a{i}"
        placeholder_val = f":v{i}"
        names[placeholder_name] = k
        values[placeholder_val] = v
        set_parts.append(f"{placeholder_name} = {placeholder_val}")

    table.update_item(
        Key={"packageId": package_id, "createdAt": created_at},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def delete_package(table, package_id: str, created_at: str) -> None:
    """Delete a launch package item."""
    table.delete_item(Key={"packageId": package_id, "createdAt": created_at})


# ────────────────────────────────────────────────────────────────────────────
# ControlPlaneState helpers  (ControlPlaneStateTable: PK=stateKey)
# ────────────────────────────────────────────────────────────────────────────

_STATE_KEY = "global"


def get_control_state(state_table, state_key: str = _STATE_KEY) -> dict | None:
    """Return the singleton control-plane state item."""
    resp = state_table.get_item(Key={"stateKey": state_key})
    return resp.get("Item")


def put_control_state(state_table, item: dict) -> None:
    """Write the singleton control-plane state item."""
    if "stateKey" not in item:
        item["stateKey"] = _STATE_KEY
    if "updatedAt" not in item:
        item["updatedAt"] = datetime.now(timezone.utc).isoformat()
    state_table.put_item(Item=item)


def set_focused_config(state_table, config_id: str, version: str) -> dict:
    """Update the focused config in the ControlPlaneStateTable."""
    updated_at = datetime.now(timezone.utc).isoformat()
    state_table.put_item(Item={
        "stateKey": _STATE_KEY,
        "focusedConfigId": config_id,
        "focusedConfigVersion": version,
        "updatedAt": updated_at,
    })
    return {
        "stateKey": _STATE_KEY,
        "focusedConfigId": config_id,
        "focusedConfigVersion": version,
        "updatedAt": updated_at,
    }