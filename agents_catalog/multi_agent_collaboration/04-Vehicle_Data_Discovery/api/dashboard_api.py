#!/usr/bin/env python3
"""Fleet Discovery API - Main Application Entry Point."""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from dependencies import init_aws_clients, rate_limiter
from services.cache_service import S3BackedMetricsCache
from routes import (
    health_router,
    fleet_router,
    scene_router,
    search_router,
    stats_router,
    config_router,
    upload_router,
    pipeline_router,
    analytics_router
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics cache instance
metrics_cache = S3BackedMetricsCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown."""
    logger.info("=" * 50)
    logger.info("Fleet Discovery API Initializing...")
    
    # Initialize AWS clients
    init_aws_clients()
    
    # Load cached metrics from S3
    logger.info("Loading cached DTO metrics from S3...")
    metrics_cache.load_from_s3_on_startup()
    
    logger.info("Listening on port 8000")
    logger.info("=" * 50)
    
    yield  # Application runs here
    
    logger.info("Shutting down...")


# Create the API app
api_app = FastAPI(title="Fleet Discovery API", lifespan=lifespan)


# Rate limiting middleware
@api_app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)


# CORS middleware
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register all routers
api_app.include_router(health_router)
api_app.include_router(fleet_router)
api_app.include_router(scene_router)
api_app.include_router(search_router)
api_app.include_router(stats_router)
api_app.include_router(config_router)
api_app.include_router(upload_router)
api_app.include_router(pipeline_router)
api_app.include_router(analytics_router)


# Main app with static files
app = FastAPI(title="Fleet Discovery Studio")


# Health check endpoint for AppRunner
@app.get("/health")
def health_check():
    """Health check endpoint for load balancers and AppRunner."""
    return {"status": "healthy"}


# Mount API under /api
app.mount("/api", api_app)

# Mount static files for frontend
try:
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
except Exception as e:
    logger.warning(f"Static files not available: {e}")


# Lambda handler
handler = Mangum(app)
