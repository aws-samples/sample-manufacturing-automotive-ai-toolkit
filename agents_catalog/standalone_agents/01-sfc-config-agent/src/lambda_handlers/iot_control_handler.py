"""WP-08 — fn-iot-control: Runtime control channel + heartbeat."""

from __future__ import annotations
import json, logging, os
from datetime import datetime, timezone
import boto3
from sfc_cp_utils import ddb as ddb_util, s3 as s3_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]
_region = os.environ.get("AWS_REGION", "us-east-1")
_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)
_iot_data = boto3.client("iot-data", region_name=_region)

_HEARTBEAT_THRESHOLD_S = 15


def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}
    package_id = path_params.get("packageId")
    try:
        pkg = ddb_util.get_package(_pkg_table, package_id)
        if not pkg:
            return _error(404, "NOT_FOUND", f"Package {package_id} not found")

        if path.endswith("/heartbeat") and method == "GET":
            return _get_heartbeat(pkg)
        if path.endswith("/control") and method == "GET":
            return _get_control_state(pkg)
        if path.endswith("/telemetry") and method == "PUT":
            return _set_toggle(pkg, "telemetry", _parse_body(event))
        if path.endswith("/diagnostics") and method == "PUT":
            return _set_toggle(pkg, "diagnostics", _parse_body(event))
        if path.endswith("/config-update") and method == "POST":
            return _push_config_update(pkg, _parse_body(event))
        if path.endswith("/restart") and method == "POST":
            return _restart(pkg)
        return _error(404, "NOT_FOUND", "Route not matched")
    except Exception as exc:
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", str(exc))


def _require_ready(pkg: dict):
    if pkg.get("status") != "READY":
        return _error(409, "CONFLICT", f"Package must be in READY state (current: {pkg.get('status')})")
    return None


def _get_control_state(pkg: dict) -> dict:
    return _ok({
        "packageId": pkg["packageId"],
        "telemetryEnabled": pkg.get("telemetryEnabled", "unknown"),
        "diagnosticsEnabled": pkg.get("diagnosticsEnabled", "unknown"),
        "lastConfigUpdateAt": pkg.get("lastConfigUpdateAt"),
        "lastConfigUpdateVersion": pkg.get("lastConfigUpdateVersion"),
        "lastRestartAt": pkg.get("lastRestartAt"),
    })


def _set_toggle(pkg: dict, toggle_type: str, body: dict) -> dict:
    err = _require_ready(pkg)
    if err:
        return err
    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        return _error(400, "BAD_REQUEST", "'enabled' must be a boolean")
    topic = f"sfc/{pkg['packageId']}/control/{toggle_type}"
    _iot_data.publish(topic=topic, qos=1, payload=json.dumps({"enabled": enabled}))
    attr_name = "telemetryEnabled" if toggle_type == "telemetry" else "diagnosticsEnabled"
    ddb_util.update_package(_pkg_table, pkg["packageId"], pkg["createdAt"], {attr_name: enabled})
    return _ok({"message": f"{toggle_type} set to {enabled}"})


def _push_config_update(pkg: dict, body: dict) -> dict:
    err = _require_ready(pkg)
    if err:
        return err
    config_id = body.get("configId")
    config_version = body.get("configVersion")
    if not config_id or not config_version:
        return _error(400, "BAD_REQUEST", "configId and configVersion required")

    # Enforce: only the same configId that was baked into the package may be pushed
    if config_id != pkg.get("configId"):
        return _error(
            400,
            "BAD_REQUEST",
            f"Config update must use the same configId as the package "
            f"(expected: {pkg.get('configId')}, got: {config_id})",
        )

    # Enforce: only versions strictly newer than the one snapshotted in the package
    pkg_config_version = pkg.get("configVersion", "")
    if config_version <= pkg_config_version:
        return _error(
            400,
            "BAD_REQUEST",
            f"Config update must be a version newer than the package's current version "
            f"(package version: {pkg_config_version}, requested: {config_version})",
        )

    s3_key = s3_util.config_s3_key(config_id, config_version)
    presigned = s3_util.generate_presigned_url(CONFIGS_BUCKET, s3_key, ttl_seconds=300)
    topic = f"sfc/{pkg['packageId']}/control/config-update"
    _iot_data.publish(topic=topic, qos=1, payload=json.dumps({"presignedUrl": presigned}))
    now = datetime.now(timezone.utc).isoformat()
    ddb_util.update_package(_pkg_table, pkg["packageId"], pkg["createdAt"], {
        "lastConfigUpdateAt": now, "lastConfigUpdateVersion": config_version,
    })
    return _ok({"message": "Config update dispatched"})


def _restart(pkg: dict) -> dict:
    err = _require_ready(pkg)
    if err:
        return err
    topic = f"sfc/{pkg['packageId']}/control/restart"
    _iot_data.publish(topic=topic, qos=1, payload=json.dumps({"restart": True}))
    now = datetime.now(timezone.utc).isoformat()
    ddb_util.update_package(_pkg_table, pkg["packageId"], pkg["createdAt"], {"lastRestartAt": now})
    return _ok({"message": "Restart command dispatched"})


def _get_heartbeat(pkg: dict) -> dict:
    package_id = pkg["packageId"]
    last_hb = pkg.get("lastHeartbeatAt")
    sfc_running = pkg.get("sfcRunning", False)
    recent_logs = pkg.get("recentLogs", [])

    live_status = "INACTIVE"
    if last_hb:
        try:
            hb_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
            age_s = (datetime.now(timezone.utc) - hb_dt).total_seconds()
            if age_s <= _HEARTBEAT_THRESHOLD_S:
                live_status = "ACTIVE" if sfc_running else "ERROR"
        except Exception:
            pass

    return _ok({
        "packageId": package_id,
        "lastHeartbeatAt": last_hb,
        "sfcRunning": sfc_running,
        "recentLogs": recent_logs,
        "liveStatus": live_status,
    })


def _parse_body(event: dict) -> dict:
    return json.loads(event.get("body") or "{}")

def _ok(body): return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, default=str)}
def _error(s, e, m): return {"statusCode": s, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": e, "message": m})}