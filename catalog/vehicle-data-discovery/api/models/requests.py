"""Request models for Fleet Discovery API."""
from pydantic import BaseModel, field_validator
from typing import List, Optional


def validate_scene_id(v: str) -> str:
    """Validate scene_id format."""
    import re
    if not re.match(r'^scene_\d{4}(_CAM_[A-Z_]+)?$', v):
        raise ValueError(f"Invalid scene_id format: {v}")
    return v


class SearchRequest(BaseModel):
    query: Optional[str] = None
    limit: Optional[int] = 12
    index_type: Optional[str] = "behavioral"
    scene_id: Optional[str] = None
    auto_query: Optional[str] = None
    source: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    uniqueness_quality: Optional[str] = None
    uniqueness_score: Optional[float] = None

    @field_validator('scene_id')
    @classmethod
    def validate_scene_id_field(cls, v):
        if v is not None:
            return validate_scene_id(v)
        return v

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        if v is not None and (v < 1 or v > 100):
            raise ValueError("limit must be between 1 and 100")
        return v


class ConfigUpdate(BaseModel):
    business_objective: str
    risk_threshold: float


class UploadRequest(BaseModel):
    data_format: str
    format_name: str
    expected_extensions: List[str]
    supported: bool
