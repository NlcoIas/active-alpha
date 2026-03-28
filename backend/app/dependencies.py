"""Shared FastAPI dependencies for the Active Alpha API."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.fmp_client import FMPClient
from app.config import settings
from app.database import SessionLocal

# Singleton FMP client instance (created on first use)
_fmp_client: FMPClient | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with SessionLocal() as session:
        yield session


def get_fmp_client() -> FMPClient:
    """Get the singleton FMP client instance.

    The client is created once and reused across requests.
    It must be closed on application shutdown via the lifespan handler.
    """
    global _fmp_client  # noqa: PLW0603
    if _fmp_client is None:
        _fmp_client = FMPClient(
            api_key=settings.fmp_api_key,
            base_url=settings.fmp_base_url,
            max_concurrent=settings.fmp_max_concurrent,
            requests_per_minute=settings.fmp_requests_per_minute,
        )
    return _fmp_client


async def shutdown_fmp_client() -> None:
    """Close the FMP client on application shutdown."""
    global _fmp_client  # noqa: PLW0603
    if _fmp_client is not None:
        await _fmp_client.close()
        _fmp_client = None


async def require_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    """Dependency that validates the admin API key from the X-API-Key header.

    Raises 401 if the key is missing or does not match.
    Returns the validated key on success.
    """
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is not configured on the server.",
        )
    if x_api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return x_api_key
