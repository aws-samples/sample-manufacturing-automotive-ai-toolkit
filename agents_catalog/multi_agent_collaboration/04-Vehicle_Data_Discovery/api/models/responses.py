"""Response models for Fleet Discovery API."""
from pydantic import BaseModel, field_validator
from typing import List, Optional


def validate_scene_id(v: str) -> str:
    """Validate scene_id format."""
    import re
    if not re.match(r'^scene[-_]\d{1,6}(_CAM_[A-Z_]+)?$', v):
        raise ValueError(f"Invalid scene_id format: {v}")
    return v


class SceneSummary(BaseModel):
    scene_id: str
    risk_score: float
    anomaly_status: str
    hil_priority: str
    description_preview: str
    tags: List[str]
    confidence_score: Optional[float] = None
    timestamp: Optional[str] = None
    hil_qualification: Optional[dict] = None

    @field_validator('scene_id')
    @classmethod
    def validate_scene_id_field(cls, v):
        return validate_scene_id(v)


class CoverageTarget(BaseModel):
    category: str
    current: int
    target: int
    status: str
    gap: int
    percentage: float
