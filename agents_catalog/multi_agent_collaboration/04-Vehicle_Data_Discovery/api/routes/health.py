"""Health routes."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
def root():
    """API Health Check"""
    return {"status": "fleet Discovery API Online", "version": "1.0.0"}
