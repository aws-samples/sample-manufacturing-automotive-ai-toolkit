"""
WP-10b — fn-agent-create-config: AI-guided SFC config creation (async).

Flow
----
POST /configs/generate
  1. Write a PENDING job record to the StateTable (PK=generate_job, SK=<jobId>).
  2. Self-invoke this Lambda asynchronously (InvocationType='Event') with
     {"__job_id": "<jobId>", ...original body...} so the API GW call returns
     immediately within the 29-second HTTP API integration limit.
  3. Return 202 { jobId }.

GET /configs/generate/{jobId}
  1. Read the job record from DynamoDB.
  2. Return { jobId, status, configId?, version?, name?, error? }.

Background invocation (triggered by self-invoke in step 2):
  - Calls AgentCore (may take up to 5 min).
  - Persists the generated config to S3 + DynamoDB.
  - Updates the job record to COMPLETE (or FAILED).

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

from sfc_cp_utils import s3 as s3_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
CONFIG_TABLE_NAME = os.environ["CONFIG_TABLE_NAME"]
STATE_TABLE_NAME = os.environ["STATE_TABLE_NAME"]
_region = os.environ.get("AWS_REGION", "us-east-1")
_function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "fn-agent-create-config")

_dynamodb = boto3.resource("dynamodb")
_cfg_table = _dynamodb.Table(CONFIG_TABLE_NAME)
_state_table = _dynamodb.Table(STATE_TABLE_NAME)

_AGENTCORE_RUNTIME_ID: str | None = None
_FILE_TYPE_CONFIG = "config"
_JOB_PREFIX = "generate_job#"


def _job_state_key(job_id: str) -> str:
    """Composite stateKey for job records: 'generate_job#<jobId>'."""
    return f"{_JOB_PREFIX}{job_id}"


# ────────────────────────────────────────────────────────────────────────────
# Lambda entry point
# ────────────────────────────────────────────────────────────────────────────


def handler(event: dict, context) -> dict:
    # Background job execution path (self-invoked asynchronously)
    if "__job_id" in event:
        return _run_background_job(event)

    method = event.get("requestContext", {}).get("http", {}).get("method", "POST")
    path = event.get("rawPath", event.get("path", ""))

    # GET /configs/generate/{jobId}  — poll job status
    if method == "GET":
        job_id = (event.get("pathParameters") or {}).get("jobId")
        if not job_id:
            return _error(400, "BAD_REQUEST", "jobId path parameter required")
        return _get_job_status(job_id)

    # POST /configs/generate  — start async generation
    if method == "POST":
        body = _parse_body(event)
        return _start_generation(body)

    return _error(405, "METHOD_NOT_ALLOWED", f"Method {method} not supported")


# ────────────────────────────────────────────────────────────────────────────
# POST — start async generation
# ────────────────────────────────────────────────────────────────────────────


def _start_generation(body: dict) -> dict:
    raw_name = (body.get("name") or "").strip()
    if not raw_name:
        return _error(400, "BAD_REQUEST", "'name' is required")

    # AI-generated configs always carry the "agent_" prefix
    name = raw_name if raw_name.startswith("agent_") else f"agent_{raw_name}"

    job_id = str(uuid.uuid4())

    # Write PENDING job record (stateKey is the only key — no sort key)
    _state_table.put_item(Item={
        "stateKey": _job_state_key(job_id),
        "jobId": job_id,
        "status": "PENDING",
        "name": name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })

    # Self-invoke asynchronously — Lambda continues running after this returns
    lambda_client = boto3.client("lambda", region_name=_region)
    payload = json.dumps({"__job_id": job_id, **body}).encode()
    lambda_client.invoke(
        FunctionName=_function_name,
        InvocationType="Event",   # fire-and-forget
        Payload=payload,
    )
    logger.info("Async job %s dispatched for config '%s'", job_id, name)

    return {
        "statusCode": 202,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"jobId": job_id, "status": "PENDING"}),
    }


# ────────────────────────────────────────────────────────────────────────────
# GET — poll job status
# ────────────────────────────────────────────────────────────────────────────


def _get_job_status(job_id: str) -> dict:
    resp = _state_table.get_item(Key={"stateKey": _job_state_key(job_id)})
    item = resp.get("Item")
    if not item:
        return _error(404, "NOT_FOUND", f"Job {job_id} not found")
    return _ok({
        "jobId": job_id,
        "status": item.get("status", "UNKNOWN"),
        "configId": item.get("configId"),
        "version": item.get("version"),
        "name": item.get("name"),
        "error": item.get("error"),
    })


# ────────────────────────────────────────────────────────────────────────────
# Background job — actual AgentCore invocation
# ────────────────────────────────────────────────────────────────────────────


def _run_background_job(event: dict) -> dict:
    job_id: str = event["__job_id"]
    logger.info("Background job %s starting", job_id)

    raw_name = (event.get("name") or "").strip()
    name = raw_name if raw_name.startswith("agent_") else f"agent_{raw_name}"
    protocol_adapters: list[str] = event.get("protocol_adapters") or ["OPCUA"]
    source_endpoints: list = event.get("source_endpoints") or []
    sfc_targets: list[str] = event.get("sfc_targets") or []
    channels_description: str = (event.get("channels_description") or "").strip()
    description: str = (event.get("description") or "").strip()
    sampling_interval_ms: int = int(event.get("sampling_interval_ms") or 1000)
    additional_context: str = (event.get("additional_context") or "").strip()

    try:
        prompt = _build_prompt(
            name=name,
            protocol_adapters=protocol_adapters,
            source_endpoints=source_endpoints,
            sfc_targets=sfc_targets,
            channels_description=channels_description,
            sampling_interval_ms=sampling_interval_ms,
            additional_context=additional_context,
        )

        session_id = str(uuid.uuid4())
        generated_config = _invoke_agentcore(prompt, session_id)

        if generated_config is None:
            _update_job(job_id, "FAILED", error="AgentCore returned no parseable JSON")
            return {}

        config_id = str(uuid.uuid4())
        version = datetime.now(timezone.utc).isoformat()
        s3_key = s3_util.config_s3_key(config_id, version)
        s3_util.put_config_json(CONFIGS_BUCKET, s3_key, generated_config)

        _cfg_table.put_item(Item={
            "file_type": _FILE_TYPE_CONFIG,
            "sort_key": f"{config_id}#{version}",
            "configId": config_id,
            "version": version,
            "name": name,
            "description": description or f"AI-generated config",
            "s3Key": s3_key,
            "status": "active",
            "createdAt": version,
            "aiGenerated": True,
            "aiGenerationSessionId": session_id,
            "aiGenerationProtocolAdapters": protocol_adapters,
            "aiGenerationSfcTargets": sfc_targets,
        })

        _update_job(job_id, "COMPLETE", config_id=config_id, version=version)
        logger.info("Job %s COMPLETE — configId=%s", job_id, config_id)

    except Exception as exc:
        logger.exception("Background job %s failed", job_id)
        _update_job(job_id, "FAILED", error=str(exc))

    return {}


def _update_job(job_id: str, status: str, *, config_id: str | None = None,
                version: str | None = None, error: str | None = None) -> None:
    update_expr = "SET #s = :s, updatedAt = :ua"
    expr_names = {"#s": "status"}
    expr_values: dict = {":s": status, ":ua": datetime.now(timezone.utc).isoformat()}
    if config_id:
        update_expr += ", configId = :cid"
        expr_values[":cid"] = config_id
    if version:
        update_expr += ", #v = :v"
        expr_names["#v"] = "version"
        expr_values[":v"] = version
    if error:
        update_expr += ", #e = :e"
        expr_names["#e"] = "error"
        expr_values[":e"] = error
    _state_table.update_item(
        Key={"stateKey": _job_state_key(job_id)},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


# ────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ────────────────────────────────────────────────────────────────────────────


def _build_prompt(*, name, protocol_adapters, source_endpoints, sfc_targets,
                  channels_description, sampling_interval_ms, additional_context="") -> str:
    adapter_section = "\n".join(f"  - {a}" for a in protocol_adapters) if protocol_adapters else "  - OPCUA"

    if source_endpoints:
        ep_lines = []
        for ep in source_endpoints:
            if isinstance(ep, dict):
                host = ep.get("host", "")
                port = ep.get("port", "")
                if host:
                    ep_lines.append(f"  - {host}" + (f":{port}" if port else ""))
            elif isinstance(ep, str) and ep.strip():
                ep_lines.append(f"  - {ep.strip()}")
        endpoint_section = "\n".join(ep_lines) if ep_lines else "  (none — use placeholder)"
    else:
        endpoint_section = "  (none — use placeholder)"

    target_section = "\n".join(f"  - {t}" for t in sfc_targets) if sfc_targets else "  - Debug"
    channel_section = channels_description or "Use sensible placeholder channels for the chosen protocol."
    extra = f"\nAdditional context:\n{additional_context}\n" if additional_context else ""

    # Derive a safe base from the config name (strip leading "agent_" prefix that
    # is already enforced, then sanitise remaining characters).
    base = name[len("agent_"):] if name.startswith("agent_") else name
    safe_base = re.sub(r"[^a-zA-Z0-9_\-]", "_", base).lower().strip("_") or "sfc_config"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"agent_{timestamp}_{safe_base}.json"

    return (
        f"Generate a complete, valid SFC (Shop Floor Connectivity) configuration JSON "
        f"for a setup named '{name}'.\n\n"
        f"SFC Protocol Adapter(s) (source side):\n{adapter_section}\n\n"
        f"Source endpoint(s):\n{endpoint_section}\n\n"
        f"SFC Target(s) (destination side):\n{target_section}\n\n"
        f"Data channels / values to collect:\n{channel_section}\n\n"
        f"Schedule sampling interval: {sampling_interval_ms} ms\n"
        f"{extra}\n"
        "Requirements:\n"
        "- The output MUST be a single valid SFC configuration JSON object.\n"
        f"- The top-level 'Description' field MUST be set to the config name: '{name}'.\n"
        "- Include all required top-level keys: AWSVersion, Description, Schedules, Sources, Targets, AdapterTypes, TargetTypes.\n"
        "- AdapterTypes must use the correct SFC adapter class "
        "(e.g. com.amazonaws.sfc.opcua.OpcuaAdapter for OPCUA, "
        "com.amazonaws.sfc.modbus.ModbusAdapter for Modbus, "
        "com.amazonaws.sfc.s7.S7Adapter for S7, etc.).\n"
        "- TargetTypes must use the correct SFC target class "
        "(e.g. com.amazonaws.sfc.awsiot.AwsIotCoreTargetWriter for AWS IoT Core, "
        "com.amazonaws.sfc.debug.DebugTargetWriter for Debug, etc.).\n"
        "IMPORTANT — saving rules:\n"
        f"- Call save_config_to_file EXACTLY ONCE, with filename '{filename}', "
        "ONLY after the config is fully complete and validated.\n"
        "- Do NOT call save_config_to_file for drafts, partial configs, or intermediate steps.\n"
        "- Only the single final call to save_config_to_file is allowed.\n"
        "After saving, confirm with a brief message — do not re-output the full JSON."
    )


# ────────────────────────────────────────────────────────────────────────────
# AgentCore invocation
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
            "actor_id": "control-plane-create-config",
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
