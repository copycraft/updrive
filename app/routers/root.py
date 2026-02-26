# Filename: app/routers/root.py
from fastapi import APIRouter
from ..config import settings

router = APIRouter()


@router.get("/", tags=["root"])
def root():
    """
    Root endpoint with app version and health.
    """
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "status": "ok",
    }