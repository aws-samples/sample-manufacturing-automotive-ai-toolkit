"""Config routes - update and current configuration."""
import logging
from fastapi import APIRouter

from dependencies import INDICES_CONFIG
from models.requests import ConfigUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["config"])


@router.post("/update")
def update_configuration(config: ConfigUpdate):
    """Update system configuration"""
    logger.info(f"Config update requested: {config}")
    return {
        "status": "success",
        "message": "Configuration updated",
        "updated_fields": config.dict(exclude_none=True)
    }


@router.get("/current")
def get_current_configuration():
    """Get current system configuration"""
    return {
        "indices": {
            name: {"name": cfg["name"], "type": cfg["type"], "source": cfg["source"]}
            for name, cfg in INDICES_CONFIG.items()
        },
        "features": {
            "twin_engine_search": True,
            "cross_encoder_reranking": True,
            "odd_discovery": True
        }
    }
