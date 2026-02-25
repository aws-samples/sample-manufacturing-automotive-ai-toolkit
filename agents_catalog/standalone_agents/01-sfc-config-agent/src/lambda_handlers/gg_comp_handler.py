"""WP-09 — fn-gg-comp: Greengrass v2 component creation."""

from __future__ import annotations
import json, logging, os
from datetime import datetime, timezone
import boto3
from sfc_cp_utils import ddb as ddb_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]
_region = os.environ.get("AWS_REGION", "us-east-1")
_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)
_gg = boto3.client("greengrassv2", region_name=_region)
_logs_client = boto3.client("logs", region_name=_region)


def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path_params = event.get("pathParameters") or {}
    package_id = path_params.get("packageId")
    try:
        pkg = ddb_util.get_package(_pkg_table, package_id)
        if not pkg:
            return _error(404, "NOT_FOUND", f"Package {package_id} not found")
        if method == "POST":
            return _create_component(pkg)
        if method == "GET":
            return _get_status(pkg)
        return _error(404, "NOT_FOUND", "Route not matched")
    except Exception as exc:
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", str(exc))


def _create_component(pkg: dict) -> dict:
    package_id = pkg["packageId"]
    if pkg.get("status") != "READY":
        return _error(409, "CONFLICT", f"Package must be READY (current: {pkg.get('status')})")

    # Check for recent errors (last 10 min)
    if _has_recent_errors(pkg):
        return _error(409, "CONFLICT", "ERROR-severity logs exist within the last 10 minutes")

    config_name = pkg.get("configId", package_id).replace("-", "_")
    version = datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M%S")
    component_name = f"com.sfc.{config_name}"

    recipe = {
        "RecipeFormatVersion": "2020-01-25",
        "ComponentName": component_name,
        "ComponentVersion": version,
        "ComponentDescription": f"SFC runner for config {config_name}",
        "ComponentPublisher": "SFC Control Plane",
        "Manifests": [{
            "Platform": {"os": "linux"},
            "Artifacts": [{
                "URI": f"s3://{CONFIGS_BUCKET}/packages/{package_id}/launch-package.zip",
                "Unarchive": "ZIP",
                "Permission": {"Read": "OWNER"},
            }],
            "Lifecycle": {
                "Install": "pip install uv && cd {artifacts:path}/runner && uv sync --frozen",
                "Run": "cd {artifacts:path}/runner && uv run runner.py",
            },
        }],
    }

    resp = _gg.create_component_version(
        inlineRecipe=json.dumps(recipe).encode()
    )
    component_arn = resp.get("arn", "")
    ddb_util.update_package(_pkg_table, package_id, pkg["createdAt"], {"ggComponentArn": component_arn})
    return _ok({"packageId": package_id, "ggComponentArn": component_arn,
                "componentName": component_name, "componentVersion": version})


def _get_status(pkg: dict) -> dict:
    return _ok({
        "packageId": pkg["packageId"],
        "ggComponentArn": pkg.get("ggComponentArn"),
        "componentName": None,
        "componentVersion": None,
        "deploymentStatus": "UNKNOWN",
    })


def _has_recent_errors(pkg: dict) -> bool:
    log_group = pkg.get("logGroupName", f"/sfc/launch-packages/{pkg['packageId']}")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - 10 * 60 * 1000
    try:
        resp = _logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=start_ms,
            endTime=now_ms,
            filterPattern='?SeverityText="ERROR"',
            limit=1,
        )
        return len(resp.get("events", [])) > 0
    except Exception:
        return False


def _ok(body): return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, default=str)}
def _error(s, e, m): return {"statusCode": s, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": e, "message": m})}