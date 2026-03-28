"""Health and readiness probe endpoints.

These live outside /api/v1 so load balancers and orchestrators
can reach them without an API prefix.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Shallow liveness probe. Always returns 200 if the process is up."""
    return {"status": "ok", "version": settings.app_version}


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Deep readiness probe. Verifies database connectivity.

    Returns 200 when the application can serve traffic, or 503 otherwise.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar_one()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready"},
        )
    except Exception:
        logger.exception("Readiness check failed: database unreachable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "error": "Database connection failed"},
        )
