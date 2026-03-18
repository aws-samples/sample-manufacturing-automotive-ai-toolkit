"""
WP-08b — fn-heartbeat-ingestion: IoT Rule Lambda action.

Receives the SFC edge heartbeat payload from IoT Core and updates the
matching LaunchPackageTable item with heartbeat state.

IoT Core invokes this function with the full heartbeat document as the event
(the SQL SELECT * result).  The edge runner is not required to include a valid
``createdAt`` value — we look up the existing item by ``packageId`` (PK) and
then call UpdateItem using the actual ``createdAt`` SK retrieved from DynamoDB.

Heartbeat payload shape:
{
    "packageId":          "63ccf300-…",
    "createdAt":          "",          # may be empty — ignored by this handler
    "timestamp":          "2026-02-28T12:28:07.184070+00:00",
    "sfcPid":             19946,
    "sfcRunning":         true,
    "telemetryEnabled":   true,
    "diagnosticsEnabled": false,
    "recentLogs":         ["…", "…"]
}
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from sfc_cp_utils import ddb as ddb_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]

_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)

# Maximum number of recent log lines to persist (keep the payload size bounded)
_MAX_LOG_LINES = 50


def handler(event: dict, _context) -> None:
    """
    IoT Rule Lambda action entry point.

    *event* is the full MQTT message payload after SQL projection
    (SELECT *, topic(2) AS packageId FROM 'sfc/+/heartbeat').
    """
    logger.info("Heartbeat event: %s", json.dumps(event, default=str))

    package_id: str | None = event.get("packageId")
    if not package_id:
        logger.error("packageId missing from heartbeat payload — dropping message")
        return

    # ------------------------------------------------------------------
    # Look up the existing launch package record to obtain the real SK
    # ------------------------------------------------------------------
    pkg = ddb_util.get_package(_pkg_table, package_id)
    if pkg is None:
        logger.warning(
            "No LaunchPackageTable item found for packageId=%s — heartbeat dropped. "
            "The package must be created via the Control Plane API before heartbeats "
            "can be ingested.",
            package_id,
        )
        return

    created_at: str = pkg["createdAt"]

    # ------------------------------------------------------------------
    # Build the update attributes from the heartbeat payload
    # ------------------------------------------------------------------
    now_iso = datetime.now(timezone.utc).isoformat()

    recent_logs = event.get("recentLogs") or []
    if not isinstance(recent_logs, list):
        recent_logs = []
    recent_logs = recent_logs[-_MAX_LOG_LINES:]

    attrs: dict = {
        "lastHeartbeatAt": now_iso,
        "sfcRunning": bool(event.get("sfcRunning", False)),
        "recentLogs": recent_logs,
    }

    # Persist optional numeric/bool fields when present in the payload
    if "sfcPid" in event:
        attrs["sfcPid"] = event["sfcPid"]
    if "telemetryEnabled" in event:
        attrs["telemetryEnabled"] = bool(event["telemetryEnabled"])
    if "diagnosticsEnabled" in event:
        attrs["diagnosticsEnabled"] = bool(event["diagnosticsEnabled"])
    if "timestamp" in event:
        attrs["lastHeartbeatTimestamp"] = event["timestamp"]

    # ------------------------------------------------------------------
    # Persist to DynamoDB via UpdateItem (uses the real createdAt SK)
    # ------------------------------------------------------------------
    try:
        ddb_util.update_package(_pkg_table, package_id, created_at, attrs)
        logger.info(
            "Heartbeat persisted for packageId=%s createdAt=%s sfcRunning=%s",
            package_id,
            created_at,
            attrs["sfcRunning"],
        )
    except Exception:
        logger.exception(
            "Failed to update heartbeat for packageId=%s createdAt=%s",
            package_id,
            created_at,
        )
        raise