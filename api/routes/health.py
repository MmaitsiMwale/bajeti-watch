"""
api/routes/health.py

Simple liveness check — Railway and other platforms ping this
to know the service is running.
"""

from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status":    "ok",
        "service":   "Bajeti Watch API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }