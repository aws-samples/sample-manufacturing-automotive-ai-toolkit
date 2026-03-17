#!/usr/bin/env python3
"""Fleet Discovery API - Main Application Entry Point."""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from dependencies import init_aws_clients, rate_limiter
from services.cache_service import S3BackedMetricsCache
from auth import require_auth
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


# Security headers middleware
@api_app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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
    allow_origins=[o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()] or ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# Register all routers
# Public - health check and debug endpoints
api_app.include_router(health_router)

# Protected - require Cognito JWT authentication
api_app.include_router(fleet_router, dependencies=[Depends(require_auth)])
api_app.include_router(scene_router, dependencies=[Depends(require_auth)])
api_app.include_router(search_router, dependencies=[Depends(require_auth)])
api_app.include_router(stats_router, dependencies=[Depends(require_auth)])
api_app.include_router(config_router, dependencies=[Depends(require_auth)])
api_app.include_router(upload_router, dependencies=[Depends(require_auth)])
api_app.include_router(pipeline_router, dependencies=[Depends(require_auth)])
api_app.include_router(analytics_router, dependencies=[Depends(require_auth)])


# Main app with static files
app = FastAPI(title="Fleet Discovery Studio")


# Health check endpoint for AppRunner
@app.get("/health")
def health_check():
    """Health check endpoint for load balancers and AppRunner."""
    return {"status": "healthy"}


# Mount API under /api
app.mount("/api", api_app)

# Serve static frontend with SPA fallback
from fastapi.responses import FileResponse
import os

STATIC_DIR = "static"

@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve static files with SPA-style routing"""
    # Try exact file
    file_path = os.path.join(STATIC_DIR, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    # Try with .html extension
    html_path = os.path.join(STATIC_DIR, f"{path}.html")
    if os.path.isfile(html_path):
        return FileResponse(html_path)
    # Try index.html in directory
    index_path = os.path.join(STATIC_DIR, path, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    # Fallback to 404.html
    return FileResponse(os.path.join(STATIC_DIR, "404.html"), status_code=404)

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# Lambda handler
handler = Mangum(app)
