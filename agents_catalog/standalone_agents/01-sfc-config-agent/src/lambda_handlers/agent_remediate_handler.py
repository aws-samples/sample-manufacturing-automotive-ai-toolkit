"""
WP-10 — fn-agent-remediate: AI-assisted SFC config remediation (async).

Flow
----
POST /packages/:packageId/remediate
  1. Write a PENDING session record to the StateTable (stateKey=remediation_job#<sessionId>).
  2. Self-invoke this Lambda asynchronously (InvocationType='Event') with
     {"__session_id": "<sessionId>", "packageId": ..., ...body} so the API GW
     call returns immediately within the 29-second HTTP API integration limit.
  3. Return 202 { sessionId, status: "PENDING" }.

GET /packages/:packageId/remediate/:sessionId
  1. Read the session record from StateTable.
  2. Return { sessionId, status, newConfigVersion?, error? }.

Background invocation (triggered by self-invoke in step 2):
  - Fetches error logs from CloudWatch.
  - Builds a prompt and calls the SFC Config AgentCore runtime.
  - Saves the corrected config as a NEW VERSION of the package's existing configId.
  - Updates the session record to COMPLETE (or FAILED).

AgentCore runtime ARN:
  env var  AGENTCORE_RUNTIME_ID   (set by CDK / AgentCore deployment tooling)
  fallback SSM /sfc-config-agent/agentcore-runtime-id
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from sfc_cp_utils import ddb as ddb_util, s3 as s3_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
CONFIG_TABLE_NAME = os.environ["CONFIG_TABLE_NAME"]
STATE_TABLE_NAME = os.environ["STATE_TABLE_NAME"]
LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]
_region = os.environ.get("AWS_REGION", "us-east-1")
_function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "fn-agent-remediate")

_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)
_cfg_table = _dynamodb.Table(CONFIG_TABLE_NAME)
_state_table = _dynamodb.Table(STATE_TABLE_NAME)
_logs_client = boto3.client("logs", region_name=_region)

_AGENTCORE_RUNTIME_ID: str | None = None
_FILE_TYPE_CONFIG = "config"
_REMEDIATION_PREFIX = "remediation_job#"


def _session_state_key(session_id: str) -> str:
    return f"{_REMEDIATION_PREFIX}{session_id}"


def _config_sort_key(config_id: str, version: str) -> str:
    return f"{config_id}#{version}"


def _ddb_get_config(config_id: str, version: str | None = None) -> dict | None:
    if version:
        resp = _cfg_table.get_item(
            Key={"file_type": _FILE_TYPE_CONFIG, "sort_key": _config_sort_key(config_id, version)}
        )
        return resp.get("Item")
    resp = _cfg_table.query(
        KeyConditionExpression=(
            Key("file_type").eq(_FILE_TYPE_CONFIG)
            & Key("sort_key").begins_with(f"{config_id}#")
        ),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def _ddb_put_config(item: dict) -> None:
    config_id = item["configId"]
    version = item["version"]
    _cfg_table.put_item(Item={
        "file_type": _FILE_TYPE_CONFIG,
        "sort_key": _config_sort_key(config_id, version),
        **item,
    })


# ────────────────────────────────────────────────────────────────────────────
# Lambda entry point
# ────────────────────────────────────────────────────────────────────────────


def handler(event: dict, context) -> dict:
    # Background job execution path (self-invoked asynchronously)
    if "__session_id" in event:
        return _run_background_job(event)

    method = event.get("requestContext", {}).get("http", {}).get("method", "POST")
    path_params = event.get("pathParameters") or {}
    package_id = path_params.get("packageId")
    session_id = path_params.get("sessionId")

    try:
        pkg = ddb_util.get_package(_pkg_table, package_id)
        if not pkg:
            return _error(404, "NOT_FOUND", f"Package {package_id} not found")

        if method == "POST" and not session_id:
            body = _parse_body(event)
            return _trigger_remediation(pkg, body)

        if method == "GET" and session_id:
            return _get_session_status(session_id)

        return _error(404, "NOT_FOUND", "Route not matched")
    except Exception as exc:
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", str(exc))


# ────────────────────────────────────────────────────────────────────────────
# POST — start async remediation
# ────────────────────────────────────────────────────────────────────────────


def _trigger_remediation(pkg: dict, body: dict) -> dict:
    package_id = pkg["packageId"]
    error_start = body.get("errorWindowStart")
    error_end = body.get("errorWindowEnd")
    if not error_start or not error_end:
        return _error(400, "BAD_REQUEST", "errorWindowStart and errorWindowEnd required")

    # Optional pre-selected error messages forwarded from the UI dialog.
    selected_errors: list[str] | None = body.get("selectedErrors") or None

    session_id = str(uuid.uuid4())

    # Write PENDING session record
    _state_table.put_item(Item={
        "stateKey": _session_state_key(session_id),
        "sessionId": session_id,
        "packageId": package_id,
        "status": "PENDING",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })

    # Self-invoke asynchronously
    lambda_client = boto3.client("lambda", region_name=_region)
    async_payload: dict = {
        "__session_id": session_id,
        "packageId": package_id,
        "errorWindowStart": error_start,
        "errorWindowEnd": error_end,
    }
    if selected_errors is not None:
        async_payload["selectedErrors"] = selected_errors
    payload = json.dumps(async_payload).encode()
    lambda_client.invoke(
        FunctionName=_function_name,
        InvocationType="Event",   # fire-and-forget
        Payload=payload,
    )
    logger.info("Async remediation session %s dispatched for package %s", session_id, package_id)

    return {
        "statusCode": 202,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"sessionId": session_id, "status": "PENDING"}),
    }


# ────────────────────────────────────────────────────────────────────────────
# GET — poll session status
# ────────────────────────────────────────────────────────────────────────────


def _get_session_status(session_id: str) -> dict:
    resp = _state_table.get_item(Key={"stateKey": _session_state_key(session_id)})
    item = resp.get("Item")
    if not item:
        return _error(404, "NOT_FOUND", f"Session {session_id} not found")
    return _ok({
        "sessionId": session_id,
        "status": item.get("status", "UNKNOWN"),
        "newConfigId": item.get("newConfigId"),
        "newConfigVersion": item.get("newConfigVersion"),
        "error": item.get("error"),
    })


# ────────────────────────────────────────────────────────────────────────────
# Background job — actual AgentCore invocation
# ────────────────────────────────────────────────────────────────────────────


def _run_background_job(event: dict) -> dict:
    session_id: str = event["__session_id"]
    package_id: str = event["packageId"]
    error_start: str = event["errorWindowStart"]
    error_end: str = event["errorWindowEnd"]
    # Pre-selected error messages forwarded from the UI dialog (optional).
    selected_errors: list[str] | None = event.get("selectedErrors") or None
    logger.info(
        "Background remediation session %s starting for package %s (selected_errors=%s)",
        session_id, package_id, len(selected_errors) if selected_errors else "all",
    )

    try:
        pkg = ddb_util.get_package(_pkg_table, package_id)
        if not pkg:
            _update_session(session_id, "FAILED", error=f"Package {package_id} not found")
            return {}

        # Use the pre-selected errors supplied by the UI, or fall back to a
        # CloudWatch query over the full error window.
        if selected_errors is not None:
            error_records = [{"body": msg} for msg in selected_errors]
            logger.info("Using %d user-selected error entries (skipping CloudWatch fetch)", len(error_records))
        else:
            log_group = pkg.get("logGroupName", f"/sfc/launch-packages/{package_id}")
            error_records = _fetch_error_logs(log_group, error_start, error_end)

        # Fetch current SFC config
        config_id = pkg.get("configId", "")
        config_version = pkg.get("configVersion", "")
        cfg_item = _ddb_get_config(config_id, config_version)
        if not cfg_item:
            _update_session(session_id, "FAILED", error=f"Config {config_id}/{config_version} not found")
            return {}

        s3_key = cfg_item.get("s3Key") or s3_util.config_s3_key(config_id, cfg_item["version"])
        sfc_config = s3_util.get_config_json(CONFIGS_BUCKET, s3_key)

        prompt = _build_remediation_prompt(
            package_id=package_id,
            session_id=session_id,
            error_records=error_records,
            sfc_config=sfc_config,
            error_start=error_start,
            error_end=error_end,
        )

        corrected_config = _invoke_agentcore(prompt, session_id)

        if corrected_config is None:
            _update_session(
                session_id, "FAILED",
                error="AgentCore returned no parseable JSON",
            )
            return {}

        # Save corrected config as a brand-new standalone config (fresh configId).
        # Using a new configId means the Config Browser shows it as a separate entry
        # (named "remediation_<timestamp>_<original-name>") rather than polluting the
        # version history of the original config or the LP's config reference.
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%dT%H%M%S")
        original_name = cfg_item.get("name", config_id)
        new_config_id = str(uuid.uuid4())
        new_version = now.isoformat()
        new_name = f"remediation_{ts}_{original_name}"
        new_s3_key = s3_util.config_s3_key(new_config_id, new_version)
        s3_util.put_config_json(CONFIGS_BUCKET, new_s3_key, corrected_config)
        new_config_item: dict = {
            "configId": new_config_id,
            "version": new_version,
            "name": new_name,
            "description": (
                f"AI-remediated config based on '{original_name}' "
                f"(package {package_id}, errors {error_start} → {error_end})"
            ),
            "s3Key": new_s3_key,
            "status": "active",
            "createdAt": new_version,
            "remediatedFromConfigId": config_id,
            "remediatedFromPackageId": package_id,
            "remediationSessionId": session_id,
            "remediationErrorWindow": f"{error_start} → {error_end}",
        }
        if cfg_item.get("tags"):
            new_config_item["tags"] = cfg_item["tags"]
        _ddb_put_config(new_config_item)

        _update_session(session_id, "COMPLETE", new_config_id=new_config_id, new_config_version=new_version)
        logger.info(
            "Session %s COMPLETE — new configId=%s name=%s version=%s",
            session_id, new_config_id, new_name, new_version,
        )

    except Exception as exc:
        logger.exception("Background remediation session %s failed", session_id)
        _update_session(session_id, "FAILED", error=str(exc))

    return {}


def _update_session(
    session_id: str,
    status: str,
    *,
    new_config_id: str | None = None,
    new_config_version: str | None = None,
    error: str | None = None,
) -> None:
    update_expr = "SET #s = :s, updatedAt = :ua"
    expr_names = {"#s": "status"}
    expr_values: dict = {":s": status, ":ua": datetime.now(timezone.utc).isoformat()}
    if new_config_id:
        update_expr += ", newConfigId = :nci"
        expr_values[":nci"] = new_config_id
    if new_config_version:
        update_expr += ", newConfigVersion = :ncv"
        expr_values[":ncv"] = new_config_version
    if error:
        update_expr += ", #e = :e"
        expr_names["#e"] = "error"
        expr_values[":e"] = error
    _state_table.update_item(
        Key={"stateKey": _session_state_key(session_id)},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


# ────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ────────────────────────────────────────────────────────────────────────────


def _build_remediation_prompt(
    *,
    package_id: str,
    session_id: str,
    error_records: list[dict],
    sfc_config: dict,
    error_start: str,
    error_end: str,
) -> str:
    """Return the remediation prompt.

    The agent is instructed to return the corrected JSON directly in its reply
    so the control plane can parse it without any additional S3 look-ups.
    Do NOT instruct the agent to call save_config_to_file — that would create
    spurious standalone config entries in the Config Browser.
    """
    error_text = "\n".join(r.get("body", "") for r in error_records[:50]) or "(no error logs found)"

    return (
        f"The following SFC process errors were observed during Launch Package `{package_id}` execution "
        f"between {error_start} and {error_end}.\n\n"
        f"Error logs:\n```\n{error_text}\n```\n\n"
        f"The SFC config currently in use:\n```json\n{json.dumps(sfc_config, indent=2)}\n```\n\n"
        "Please diagnose the root cause of the errors and return a corrected, complete, valid SFC "
        "configuration JSON. Preserve all working parts of the config — only fix what is causing the errors.\n\n"
        "Requirements:\n"
        "- The output MUST be a single valid SFC configuration JSON object.\n"
        "- Include all required top-level keys: AWSVersion, Description, Schedules, Sources, Targets, "
        "AdapterTypes, TargetTypes.\n"
        "- Do NOT change working adapter types, target types, or schedule intervals unless they are "
        "directly implicated in the errors.\n"
        "Return ONLY the corrected JSON object — no prose, no markdown fences, no extra text."
    )


# ────────────────────────────────────────────────────────────────────────────
# AgentCore invocation (matches agent_create_config_handler.py exactly)
# ────────────────────────────────────────────────────────────────────────────


def _get_agentcore_runtime_id() -> str | None:
    global _AGENTCORE_RUNTIME_ID
    if _AGENTCORE_RUNTIME_ID:
        return _AGENTCORE_RUNTIME_ID
    runtime_id = os.environ.get("AGENTCORE_RUNTIME_ID", "")
    if not runtime_id:
        try:
            ssm = boto3.client("ssm", region_name=_region)
            runtime_id = ssm.get_parameter(
                Name="/sfc-config-agent/agentcore-runtime-id"
            )["Parameter"]["Value"]
        except Exception as exc:
            logger.warning("Could not resolve AgentCore runtime ID from SSM: %s", exc)
            return None
    _AGENTCORE_RUNTIME_ID = runtime_id
    return runtime_id


def _invoke_agentcore(prompt: str, session_id: str) -> dict | None:
    runtime_id = _get_agentcore_runtime_id()
    if not runtime_id:
        logger.warning("AGENTCORE_RUNTIME_ID not set; skipping AgentCore invocation")
        return None
    try:
        client = boto3.client("bedrock-agentcore", region_name=_region)
        payload = json.dumps({
            "prompt": prompt,
            "session_id": session_id,
            "actor_id": "control-plane-remediation",
        }).encode()

        resp = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_id,
            runtimeSessionId=session_id,
            payload=payload,
            contentType="application/json",
            accept="application/json",
        )

        raw = resp.get("body") or resp.get("response") or resp.get("outputText", b"")
        if hasattr(raw, "read"):
            body_bytes = raw.read()
        elif isinstance(raw, (bytes, bytearray)):
            body_bytes = raw
        else:
            body_bytes = str(raw).encode()

        body_str = body_bytes.decode("utf-8", errors="ignore")
        logger.info("AgentCore response (truncated): %s", body_str[:500])

        try:
            outer = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            outer = {}

        agent_text = outer.get("result", body_str)
        if isinstance(agent_text, dict):
            return agent_text
        return _extract_json(agent_text)

    except Exception as exc:
        logger.error("AgentCore invocation failed: %s", exc)
        return None


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ────────────────────────────────────────────────────────────────────────────
# Log fetching
# ────────────────────────────────────────────────────────────────────────────


def _fetch_error_logs(log_group: str, start_iso: str, end_iso: str) -> list[dict]:
    try:
        start_ms = int(datetime.fromisoformat(start_iso.replace("Z", "+00:00")).timestamp() * 1000)
        end_ms = int(datetime.fromisoformat(end_iso.replace("Z", "+00:00")).timestamp() * 1000)
        resp = _logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=start_ms,
            endTime=end_ms,
            filterPattern='?SeverityText="ERROR"',
            limit=100,
        )
        return [{"body": e.get("message", "")} for e in resp.get("events", [])]
    except Exception as exc:
        logger.warning("Failed to fetch error logs: %s", exc)
        return []


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, default=str)}


def _error(status: int, error: str, message: str) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": error, "message": message})}
