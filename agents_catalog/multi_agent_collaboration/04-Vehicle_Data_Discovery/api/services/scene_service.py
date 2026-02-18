"""Scene processing service."""
import ast
import logging
import re

logger = logging.getLogger(__name__)


def validate_scene_id(scene_id: str) -> str:
    """Validate and normalize scene ID format."""
    normalized = scene_id.replace('-', '_')
    if not re.match(r'^scene_\d{4}$', normalized):
        raise ValueError(f"Invalid scene_id format: {scene_id}")
    return normalized


def safe_parse_agent_analysis(agent_data: dict) -> dict:
    """Parse agent analysis from summary string or dict."""
    try:
        analysis = agent_data.get("analysis", {})
        if not isinstance(analysis, dict):
            return {}

        summary = analysis.get("summary", {})

        if isinstance(summary, dict):
            return summary

        if isinstance(summary, str) and summary.startswith("{"):
            try:
                return ast.literal_eval(summary.strip())
            except Exception:
                pass
        return {}
    except Exception as e:
        logger.error(f"Failed to parse agent analysis: {e}")
        return {}


def extract_anomaly_summary(anomaly_findings):
    """Extract anomaly summary from findings."""
    if not anomaly_findings:
        return {"detected": False, "count": 0, "types": []}
    
    if isinstance(anomaly_findings, dict):
        return {
            "detected": anomaly_findings.get("anomaly_detected", False),
            "count": anomaly_findings.get("anomaly_count", 0),
            "types": anomaly_findings.get("anomaly_types", [])
        }
    
    if isinstance(anomaly_findings, list):
        return {
            "detected": len(anomaly_findings) > 0,
            "count": len(anomaly_findings),
            "types": [f.get("type", "unknown") for f in anomaly_findings if isinstance(f, dict)]
        }
    
    return {"detected": False, "count": 0, "types": []}


def beautify_for_ui(text: str, max_length: int = 100) -> str:
    """Clean and truncate text for UI display."""
    if not text:
        return ""
    
    cleaned = re.sub(r'\s+', ' ', str(text)).strip()
    
    if len(cleaned) <= max_length:
        return cleaned
    
    return cleaned[:max_length-3] + "..."


def format_hil_priority(priority: str) -> str:
    """Normalize HIL priority string."""
    if not priority:
        return "MEDIUM"
    
    priority_upper = str(priority).upper().strip()
    
    valid_priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    if priority_upper in valid_priorities:
        return priority_upper
    
    return "MEDIUM"


def format_tags_for_ui(tags: list) -> list:
    """Clean and format tags for UI display."""
    if not tags:
        return []
    
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    
    cleaned = []
    for tag in tags:
        if isinstance(tag, str):
            tag = tag.strip()
            if tag and len(tag) < 50:
                cleaned.append(tag)
    
    return cleaned[:10]  # Limit to 10 tags


def apply_metadata_filter(scenes: list, filter_id: str) -> list:
    """Apply metadata filter to scene list."""
    if not filter_id or filter_id == "all":
        return scenes

    filter_map = {
        "critical": ("anomaly_status", "CRITICAL"),
        "deviation": ("anomaly_status", "DEVIATION"),
        "normal": ("anomaly_status", "NORMAL"),
        "hil_high": ("hil_priority", "HIGH"),
        "hil_medium": ("hil_priority", "MEDIUM"),
        "hil_low": ("hil_priority", "LOW"),
    }

    field, value = filter_map.get(filter_id, (None, None))
    if field and value:
        return [s for s in scenes if getattr(s, field, None) == value]

    return scenes
