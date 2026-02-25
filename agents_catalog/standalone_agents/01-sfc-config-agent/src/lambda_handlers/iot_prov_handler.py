"""WP-05 — fn-iot-prov: IoT provisioning lifecycle handler."""

from __future__ import annotations
import json, logging, os, uuid
from datetime import datetime, timezone
import boto3
from sfc_cp_utils import ddb as ddb_util
from sfc_cp_utils import iot as iot_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]
_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)
_region = os.environ.get("AWS_REGION", "us-east-1")


def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path_params = event.get("pathParameters") or {}
    package_id = path_params.get("packageId")
    try:
        if method == "POST":
            return _reprovision(package_id)
        if method == "GET":
            return _get_iot_status(package_id)
        if method == "DELETE":
            return _revoke_iot(package_id)
        return _error(404, "NOT_FOUND", "Route not matched")
    except Exception as exc:
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", str(exc))


def _reprovision(source_pkg_id: str) -> dict:
    source = ddb_util.get_package(_pkg_table, source_pkg_id)
    if not source:
        return _error(404, "NOT_FOUND", f"Package {source_pkg_id} not found")
    new_pkg_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    prov = iot_util.provision_thing(new_pkg_id, _region)
    item = {
        "packageId": new_pkg_id,
        "createdAt": created_at,
        "configId": source.get("configId", ""),
        "configVersion": source.get("configVersion", ""),
        "status": "READY",
        "iotThingName": prov["thingName"],
        "iotCertArn": prov["certArn"],
        "iotRoleAliasArn": prov["roleAliasArn"],
        "iamRoleArn": prov["iamRoleArn"],
        "logGroupName": prov["logGroupName"],
        "sourcePackageId": source_pkg_id,
        "telemetryEnabled": True,
        "diagnosticsEnabled": False,
    }
    ddb_util.put_package(_pkg_table, item)
    return _ok({"packageId": new_pkg_id, "status": "READY", "iotThingName": prov["thingName"],
                "iotCertArn": prov["certArn"], "iotRoleAliasArn": prov["roleAliasArn"],
                "iamRoleArn": prov["iamRoleArn"]})


def _get_iot_status(package_id: str) -> dict:
    pkg = ddb_util.get_package(_pkg_table, package_id)
    if not pkg:
        return _error(404, "NOT_FOUND", f"Package {package_id} not found")
    return _ok({"packageId": package_id, "iotThingName": pkg.get("iotThingName"),
                "iotCertArn": pkg.get("iotCertArn"), "iotRoleAliasArn": pkg.get("iotRoleAliasArn"),
                "iamRoleArn": pkg.get("iamRoleArn"), "status": pkg.get("status")})


def _revoke_iot(package_id: str) -> dict:
    pkg = ddb_util.get_package(_pkg_table, package_id)
    if not pkg:
        return _error(404, "NOT_FOUND", f"Package {package_id} not found")
    thing_name = pkg.get("iotThingName", f"sfc-{package_id}")
    cert_arn = pkg.get("iotCertArn", "")
    role_alias = pkg.get("iotRoleAliasArn", "").split("/")[-1]
    iam_role = f"sfc-edge-role-{package_id}"
    iot_util.revoke_and_delete_thing(thing_name, cert_arn, role_alias, iam_role, _region)
    ddb_util.update_package(_pkg_table, package_id, pkg["createdAt"], {"status": "ERROR"})
    return _ok({"message": f"IoT resources revoked for package {package_id}"})


def _ok(body): return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, default=str)}
def _error(s, e, m): return {"statusCode": s, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": e, "message": m})}