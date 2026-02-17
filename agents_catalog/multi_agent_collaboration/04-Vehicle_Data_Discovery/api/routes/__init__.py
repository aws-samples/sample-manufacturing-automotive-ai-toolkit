"""Routes package for Fleet Discovery API."""
from .health import router as health_router
from .fleet import router as fleet_router
from .scene import router as scene_router
from .search import router as search_router
from .stats import router as stats_router
from .config import router as config_router
from .upload import router as upload_router
from .pipeline import router as pipeline_router
from .analytics import router as analytics_router

__all__ = [
    "health_router",
    "fleet_router",
    "scene_router",
    "search_router",
    "stats_router",
    "config_router",
    "upload_router",
    "pipeline_router",
    "analytics_router",
]
