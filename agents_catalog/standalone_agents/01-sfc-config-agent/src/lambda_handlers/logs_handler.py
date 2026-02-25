"""WP-07 — fn-logs: CloudWatch OTEL log retrieval."""

from __future__ import annotations
import json, logging, os
from datetime import datetime, timezone
import boto3
from sfc_cp_utils import ddb as ddb_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]
_region = os.environ.get("AWS_REGION", "us-east-1")
_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)
_logs = boto3.client("logs", region_name=_region)

ERROR_FILTER_PATTERN = '?SeverityText="ERROR" ?SeverityNumber=17 ?SeverityNumber=18 ?SeverityNumber=19 ?SeverityNumber=20 ?SeverityNumber=21 ?SeverityNumber=22 ?SeverityNumber=23 ?SeverityNumber=24'


def handler(event: dict, context) -> dict:
    path = event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}
    qs = event.get("queryStringParameters") or {}
    package_id = path_params.get("packageId")
    try:
        pkg = ddb_util.get_package(_pkg_table, package_id)
        if not pkg:
            return _error(404, "NOT_FOUND", f"Package {package_id} not found")
        log_group = pkg.get("logGroupName", f"/sfc/launch-packages/{package_id}")
        # Check log group exists
        if pkg.get("status") == "PROVISIONING":
            return _error(404, "NOT_FOUND", "Package still provisioning — log group not yet available")
        error_only = path.endswith("/errors")
        return _get_logs(log_group, qs, error_only)
    except Exception as exc:
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", str(exc))


def _get_logs(log_group: str, qs: dict, error_only: bool) -> dict:
    kwargs: dict = {"logGroupName": log_group}
    if qs.get("startTime"):
        kwargs["startTime"] = _to_epoch_ms(qs["startTime"])
    if qs.get("endTime"):
        kwargs["endTime"] = _to_epoch_ms(qs["endTime"])
    if qs.get("nextToken"):
        kwargs["nextToken"] = qs["nextToken"]
    kwargs["limit"] = min(int(qs.get("limit", 200)), 1000)
    if error_only:
        kwargs["filterPattern"] = ERROR_FILTER_PATTERN
    try:
        resp = _logs.filter_log_events(**kwargs)
    except _logs.exceptions.ResourceNotFoundException:
        return _error(404, "NOT_FOUND", f"Log group {log_group} not found")
    records = [_parse_log_event(e) for e in resp.get("events", [])]
    result: dict = {"records": records}
    if resp.get("nextToken"):
        result["nextToken"] = resp["nextToken"]
    return _ok(result)


def _parse_log_event(event: dict) -> dict:
    msg = event.get("message", "")
    severity = "INFO"
    severity_num = 9
    for sev, num in [("ERROR", 17), ("WARN", 13), ("DEBUG", 5)]:
        if sev in msg.upper():
            severity = sev
            severity_num = num
            break
    return {
        "timestamp": datetime.fromtimestamp(event["timestamp"] / 1000, tz=timezone.utc).isoformat(),
        "severityText": severity,
        "severityNumber": severity_num,
        "body": msg.strip(),
    }


def _to_epoch_ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def _ok(body): return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, default=str)}
def _error(s, e, m): return {"statusCode": s, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": e, "message": m})}