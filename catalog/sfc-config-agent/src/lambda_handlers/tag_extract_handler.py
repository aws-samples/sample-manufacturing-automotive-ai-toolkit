"""
fn-tag-extract — Synchronous PLC tag & endpoint extraction using Amazon Bedrock.

POST /configs/tags/extract
  Body: { "protocol": str, "docText": str (≤100,000 chars) }
  Returns: { "plcs": [ { plcId, endpoint, tags } ] }
  Errors:
    400 BAD_REQUEST              — docText missing
    422 INVALID_EXTRACTION_RESPONSE — Bedrock returned output that fails schema validation
    500 EXTRACTION_FAILED        — unexpected error

If the response fails schema validation the caller receives a 422 with a
human-readable message describing which field is wrong, so the UI can offer
a "Retry" option.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_MODEL_ID = os.environ.get(
    "TAG_EXTRACT_MODEL_ID",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)
_INFERENCE_REGION = os.environ.get("AWS_BEDROCK_INFERENCE_REGION", "us-east-1")
_MAX_CHARS = 100_000

_bedrock_runtime = None


def _get_bedrock_client():
    global _bedrock_runtime
    if _bedrock_runtime is None:
        _bedrock_runtime = boto3.client(
            "bedrock-runtime", region_name=_INFERENCE_REGION
        )
    return _bedrock_runtime


class _ExtractionValidationError(Exception):
    """Raised when Bedrock output does not match the expected schema."""


# ─── Lambda entry point ───────────────────────────────────────────────────────


def handler(event: dict, context) -> dict:
    method = (
        event.get("requestContext", {}).get("http", {}).get("method", "POST").upper()
    )
    if method != "POST":
        return _error(405, "METHOD_NOT_ALLOWED", f"Method {method} not supported")

    body = _parse_body(event)
    protocol: str = (body.get("protocol") or "").strip()
    doc_text: str = (body.get("docText") or "").strip()

    if not doc_text:
        return _error(400, "BAD_REQUEST", "'docText' is required")

    if len(doc_text) > _MAX_CHARS:
        doc_text = doc_text[:_MAX_CHARS]
        logger.warning("docText truncated to %d chars", _MAX_CHARS)

    try:
        result = _extract(protocol=protocol, doc_text=doc_text)
        return _ok(result)
    except _ExtractionValidationError as exc:
        logger.warning("Tag extraction schema validation failed: %s", exc)
        return _error(422, "INVALID_EXTRACTION_RESPONSE", str(exc))
    except Exception as exc:
        logger.exception("Tag extraction failed")
        return _error(500, "EXTRACTION_FAILED", str(exc))


# ─── Core extraction ──────────────────────────────────────────────────────────


def _extract(protocol: str, doc_text: str) -> dict:
    """Call Bedrock synchronously, validate, and return { plcs: [...] }."""
    prompt = _build_prompt(protocol, doc_text)

    client = _get_bedrock_client()
    response = client.invoke_model(
        modelId=_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )

    raw_body = response["body"].read().decode("utf-8")
    outer = json.loads(raw_body)

    text_content = ""
    for block in outer.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text_content += block.get("text", "")

    logger.info("Claude response (first 500 chars): %s", text_content[:500])

    extracted = _parse_json_from_text(text_content)
    if extracted is None:
        raise _ExtractionValidationError(
            "Could not parse a JSON object from the model response — "
            "try again or provide more structured documentation text."
        )

    _validate_schema(extracted)
    return {"plcs": extracted.get("plcs", [])}


# ─── Schema validation ────────────────────────────────────────────────────────


def _validate_schema(data: Any) -> None:
    """
    Raise _ExtractionValidationError if data does not match:
      { plcs: [ { plcId: str, endpoint?: {...}, tags: [ { address, name, dataType } ] } ] }
    """
    if not isinstance(data, dict):
        raise _ExtractionValidationError(
            f"Expected a JSON object, got {type(data).__name__}"
        )

    plcs = data.get("plcs")
    if not isinstance(plcs, list):
        raise _ExtractionValidationError(
            f"'plcs' must be an array, got {type(plcs).__name__ if plcs is not None else 'null'}"
        )

    for i, plc in enumerate(plcs):
        if not isinstance(plc, dict):
            raise _ExtractionValidationError(f"plcs[{i}] must be an object")
        if not isinstance(plc.get("plcId"), str) or not plc["plcId"].strip():
            raise _ExtractionValidationError(
                f"plcs[{i}].plcId must be a non-empty string"
            )
        tags = plc.get("tags")
        if not isinstance(tags, list):
            raise _ExtractionValidationError(f"plcs[{i}].tags must be an array")
        for j, tag in enumerate(tags):
            if not isinstance(tag, dict):
                raise _ExtractionValidationError(f"plcs[{i}].tags[{j}] must be an object")
            for req_field in ("address", "name", "dataType"):
                if not isinstance(tag.get(req_field), str) or not tag[req_field].strip():
                    raise _ExtractionValidationError(
                        f"plcs[{i}].tags[{j}].{req_field} must be a non-empty string"
                    )


# ─── Prompt ───────────────────────────────────────────────────────────────────


def _build_prompt(protocol: str, doc_text: str) -> str:
    protocol_hint = f" for the **{protocol}** protocol" if protocol else ""
    return f"""You are an industrial automation expert. Analyze the following PLC / device documentation{protocol_hint} and extract a structured list of PLC devices, each with their network endpoint and tag definitions.

Return ONLY a single valid JSON object matching this exact schema — no explanation, no markdown, no extra text outside the JSON:

{{
  "plcs": [
    {{
      "plcId": "<PLC or device identifier, e.g. 'PLC_1' or 'Press_Line_A'>",
      "endpoint": {{
        "ip": "<IP address or hostname, or null if not found>",
        "port": "<port number as string, or null if not found>",
        "description": "<context description or empty string>"
      }},
      "tags": [
        {{
          "address": "<tag address exactly as written, e.g. '%DB120:242:REAL' or 'ns=2;i=1001' or '40001'>",
          "name": "<human-readable tag name>",
          "dataType": "<data type, e.g. REAL, INT, BOOL, DINT, WORD, STRING>",
          "description": "<brief description or empty string>"
        }}
      ]
    }}
  ]
}}

Rules:
- One PLC/device → single-element "plcs" array. Multiple devices → one entry each.
- Include ALL tags found — do not filter, deduplicate or limit.
- Associate each tag with the correct PLC/device.
- If a PLC has no endpoint info, set ip/port to null.
- If no tags are found anywhere, return an empty "plcs" array.

Documentation text:
---
{doc_text}
---

JSON response:"""


# ─── JSON extraction helper ───────────────────────────────────────────────────


def _parse_json_from_text(text: str) -> dict | None:
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


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw or {}


def _ok(body: dict) -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _error(status: int, error: str, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": error, "message": message}),
    }
