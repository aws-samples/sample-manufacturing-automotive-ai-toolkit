"""
WP-10 — fn-agent-remediate: AI-assisted SFC config remediation.

Calls the SFC Config Agent running as a BedrockAgentCoreApp via the
bedrock-agentcore runtime API (invoke_agent_runtime), NOT the Bedrock
managed agent runtime (bedrock-agent-runtime / InvokeAgent).

The AgentCore runtime ID is read from:
  env var  AGENTCORE_RUNTIME_ID   (set by CDK / AgentCore deployment tooling)
  fallback SSM /sfc-config-agent/agentcore-runtime-id
"""

from __future__ import annotations
import json, logging, os, re, uuid
from datetime import datetime, timezone
import boto3
from sfc_cp_utils import ddb as ddb_util, s3 as s3_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
CONFIG_TABLE_NAME = os.environ["CONFIG_TABLE_NAME"]
LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]
_region = os.environ.get("AWS_REGION", "us-east-1")

_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)
_cfg_table = _dynamodb.Table(CONFIG_TABLE_NAME)
_logs_client = boto3.client("logs", region_name=_region)

# AgentCore runtime ID — resolved lazily
_AGENTCORE_RUNTIME_ID: str | None = None


def _get_agentcore_runtime_id() -> str | None:
    global _AGENTCORE_RUNTIME_ID
    if _AGENTCORE_RUNTIME_ID:
        return _AGENTCORE_RUNTIME_ID
    # Try env var first (injected by CDK)
    runtime_id = os.environ.get("AGENTCORE_RUNTIME_ID", "")
    if not runtime_id:
        # Fall back to SSM
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


def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
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
            return _get_session_status(pkg, session_id)
        return _error(404, "NOT_FOUND", "Route not matched")
    except Exception as exc:
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", str(exc))


def _trigger_remediation(pkg: dict, body: dict) -> dict:
    package_id = pkg["packageId"]
    error_start = body.get("errorWindowStart")
    error_end = body.get("errorWindowEnd")
    if not error_start or not error_end:
        return _error(400, "BAD_REQUEST", "errorWindowStart and errorWindowEnd required")

    # Fetch error log records
    log_group = pkg.get("logGroupName", f"/sfc/launch-packages/{package_id}")
    error_records = _fetch_error_logs(log_group, error_start, error_end)

    # Fetch current SFC config
    config_id = pkg.get("configId", "")
    config_version = pkg.get("configVersion", "")
    cfg_item = ddb_util.get_config(_cfg_table, config_id, config_version)
    if not cfg_item:
        return _error(404, "NOT_FOUND", f"Config {config_id}/{config_version} not found")
    s3_key = cfg_item.get("s3Key") or s3_util.config_s3_key(config_id, cfg_item["version"])
    sfc_config = s3_util.get_config_json(CONFIGS_BUCKET, s3_key)

    # Build prompt for the SFC Config AgentCore
    error_text = "\n".join(r.get("body", "") for r in error_records[:50])
    prompt = (
        f"The following SFC process errors were observed during Launch Package `{package_id}` execution.\n\n"
        f"Error logs:\n```\n{error_text}\n```\n\n"
        f"The SFC config used:\n```json\n{json.dumps(sfc_config, indent=2)}\n```\n\n"
        "Please diagnose the root cause and return a corrected SFC config JSON. "
        "Respond with ONLY valid JSON, no explanation text outside the JSON block."
    )

    session_id = str(uuid.uuid4())

    # Invoke the AgentCore runtime (BedrockAgentCoreApp HTTP endpoint)
    corrected_config = _invoke_agentcore(prompt, session_id)
    if corrected_config is None:
        return _error(504, "TIMEOUT", "AgentCore invocation timed out or returned no parseable JSON")

    # Persist corrected config as new version
    new_version = datetime.now(timezone.utc).isoformat()
    new_s3_key = s3_util.config_s3_key(config_id, new_version)
    s3_util.put_config_json(CONFIGS_BUCKET, new_s3_key, corrected_config)
    ddb_util.put_config(_cfg_table, {
        "configId": config_id,
        "version": new_version,
        "name": cfg_item.get("name", config_id),
        "description": f"AI-remediated from package {package_id}",
        "s3Key": new_s3_key,
        "status": "active",
        "createdAt": new_version,
        "remediatedFromPackageId": package_id,
        "remediationSessionId": session_id,
    })

    return _ok({
        "sessionId": session_id,
        "newConfigVersion": new_version,
        "correctedConfig": corrected_config,
    })


def _get_session_status(pkg: dict, session_id: str) -> dict:
    # Synchronous flow — always COMPLETE if record was persisted
    return _ok({
        "sessionId": session_id,
        "status": "COMPLETE",
        "newConfigVersion": None,
        "correctedConfig": None,
    })


def _invoke_agentcore(prompt: str, session_id: str) -> dict | None:
    """
    Call the SFC Config Agent via the BedrockAgentCore runtime API.

    Uses boto3 client "bedrock-agentcore" + invoke_agent_runtime(), which
    sends an HTTP POST to the AgentCore runtime endpoint and returns the
    streamed response body.

    The agent.py @app.entrypoint expects:
      { "prompt": "<user message>", "session_id": "<stable id>", "actor_id": "..." }
    and returns:
      { "result": "<agent response text>" }
    """
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
            agentRuntimeId=runtime_id,
            sessionId=session_id,
            payload=payload,
            contentType="application/json",
            accept="application/json",
        )

        # Response body is a streaming blob — read it fully
        body_bytes = resp["response"].read() if hasattr(resp.get("response", ""), "read") else resp.get("body", b"")
        if not body_bytes:
            # Some SDK versions return the body directly
            body_bytes = resp.get("outputText", b"")
        if isinstance(body_bytes, str):
            body_bytes = body_bytes.encode()

        body_str = body_bytes.decode("utf-8", errors="ignore")
        logger.info("AgentCore response (truncated): %s", body_str[:500])

        # Parse outer wrapper {"result": "<agent text>"}
        outer = json.loads(body_str) if body_str else {}
        agent_text = outer.get("result", body_str)

        return _extract_json(agent_text)

    except Exception as exc:
        logger.error("AgentCore invocation failed: %s", exc)
        return None


def _extract_json(text: str) -> dict | None:
    """Extract the first JSON object from agent response text."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Bare JSON object
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


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


def _parse_body(event: dict) -> dict:
    return json.loads(event.get("body") or "{}")


def _ok(body): return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, default=str)}
def _error(s, e, m): return {"statusCode": s, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": e, "message": m})}