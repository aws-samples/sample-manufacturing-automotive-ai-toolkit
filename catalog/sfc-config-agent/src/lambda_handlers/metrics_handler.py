"""fn-metrics — CloudWatch metrics for a Launch Package → Chart.js dataset array.

POST /packages/{packageId}/metrics
Body (all optional):
  {
    "lookbackMinutes": 15,   # default 15, max 1440
    "category": "Target"     # "Target" | "Core" | "Adapter" | "All"  (default "Target")
  }

Response:
  [
    {
      "label": "<MetricName> · <Type> · <Source>",
      "data":  [{"x": "<ISO-timestamp>", "y": <float>}, ...],   # sorted ascending
      "borderColor": "#hex",
      "backgroundColor": "#hex33",
      "tension": 0.3,
      "fill": false,
      "pointRadius": 2
    },
    ...
  ]
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_region = os.environ.get("AWS_REGION", "us-east-1")
_cw = boto3.client("cloudwatch", region_name=_region)

_SFC_NAMESPACE = "SFC"
_DEFAULT_LOOKBACK_MINUTES = 15
_MAX_LOOKBACK_MINUTES = 1440
_PERIOD_SECONDS = 60
_DEFAULT_CATEGORY = "Target"

# Rotating color palette for chart series
_COLORS = [
    "#4ade80",  # green
    "#60a5fa",  # blue
    "#f472b6",  # pink
    "#facc15",  # yellow
    "#fb923c",  # orange
    "#a78bfa",  # violet
    "#34d399",  # emerald
    "#38bdf8",  # sky
    "#f87171",  # red
    "#e879f9",  # fuchsia
    "#2dd4bf",  # teal
    "#fbbf24",  # amber
]


def handler(event: dict, context) -> dict:
    path_params = event.get("pathParameters") or {}
    package_id = path_params.get("packageId")
    if not package_id:
        return _error(400, "BAD_REQUEST", "Missing packageId path parameter")

    body = _parse_body(event)
    lookback = min(
        int(body.get("lookbackMinutes", _DEFAULT_LOOKBACK_MINUTES)),
        _MAX_LOOKBACK_MINUTES,
    )
    category = body.get("category", _DEFAULT_CATEGORY)  # "Target"|"Core"|"Adapter"|"All"

    try:
        datasets = _build_datasets(package_id, lookback, category)
        return _ok(datasets)
    except Exception as exc:
        logger.exception("Error fetching metrics for package %s", package_id)
        return _error(500, "INTERNAL_ERROR", str(exc))


# ── Core logic ────────────────────────────────────────────────────────────────

def _build_datasets(package_id: str, lookback_minutes: int, category: str) -> list[dict]:
    """Discover all SFC metrics for this package, optionally filtered by Category,
    fetch their time-series data, and return a Chart.js dataset array."""

    # 1. Discover metrics under dimension LaunchPackage=<packageId>
    metrics = _list_metrics(package_id)
    if not metrics:
        logger.info("No SFC metrics found for package %s", package_id)
        return []

    # 2. Filter by Category dimension (unless "All")
    if category != "All":
        metrics = [m for m in metrics if _get_dim(m, "Category") == category]
    if not metrics:
        logger.info(
            "No metrics found for package %s with category=%s", package_id, category
        )
        return []

    # 3. Build GetMetricData queries — one per discovered metric
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(minutes=lookback_minutes)

    queries = []
    for idx, metric in enumerate(metrics):
        queries.append({
            "Id": f"m{idx}",
            "MetricStat": {
                "Metric": {
                    "Namespace": metric["Namespace"],
                    "MetricName": metric["MetricName"],
                    "Dimensions": metric["Dimensions"],
                },
                "Period": _PERIOD_SECONDS,
                "Stat": "Average",
            },
            "ReturnData": True,
        })

    # GetMetricData supports max 500 queries per call; chunk if needed
    all_results: dict[str, dict] = {}
    for chunk_start in range(0, len(queries), 500):
        chunk = queries[chunk_start : chunk_start + 500]
        paginator = _cw.get_paginator("get_metric_data")
        for page in paginator.paginate(
            MetricDataQueries=chunk,
            StartTime=start_time,
            EndTime=now,
            ScanBy="TimestampAscending",
        ):
            for result in page.get("MetricDataResults", []):
                all_results[result["Id"]] = result

    # 4. Transform results → Chart.js datasets
    datasets = []
    for idx, metric in enumerate(metrics):
        result = all_results.get(f"m{idx}", {})
        timestamps = result.get("Timestamps", [])
        values = result.get("Values", [])

        if not timestamps:
            continue  # skip empty series

        # Sort ascending by timestamp (ScanBy should already guarantee this,
        # but we sort explicitly for safety)
        pairs = sorted(zip(timestamps, values), key=lambda p: p[0])

        data_points = [
            {"x": ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "y": round(val, 4)}
            for ts, val in pairs
        ]

        label = _make_label(metric)
        color = _COLORS[idx % len(_COLORS)]

        datasets.append({
            "label": label,
            "data": data_points,
            "borderColor": color,
            "backgroundColor": color + "33",  # 20% alpha fill
            "tension": 0.3,
            "fill": False,
            "pointRadius": 2,
        })

    return datasets


def _list_metrics(package_id: str) -> list[dict]:
    """Return all SFC metrics that have the LaunchPackage dimension set to package_id."""
    results = []
    paginator = _cw.get_paginator("list_metrics")
    for page in paginator.paginate(
        Namespace=_SFC_NAMESPACE,
        Dimensions=[{"Name": "LaunchPackage", "Value": package_id}],
    ):
        results.extend(page.get("Metrics", []))
    return results


def _get_dim(metric: dict, name: str) -> str:
    """Return the value of a named dimension from a metric descriptor."""
    for dim in metric.get("Dimensions", []):
        if dim["Name"] == name:
            return dim["Value"]
    return ""


def _make_label(metric: dict) -> str:
    """Build a human-readable Chart.js series label.

    Format:  <MetricName> · <Type> · <Source>
    e.g.     ValuesRead · SimulatorAdapter · SIMULATOR:SimulatorSource
             WriteSuccess · SfcCore · SfcCore
    """
    metric_name = metric.get("MetricName", "?")
    type_ = _get_dim(metric, "Type")
    source = _get_dim(metric, "Source")
    parts = [metric_name]
    if type_:
        parts.append(type_)
    if source and source != type_:
        parts.append(source)
    return " · ".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_body(event: dict) -> dict:
    try:
        return json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _ok(body):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _error(status: int, error: str, message: str):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": error, "message": message}),
    }
