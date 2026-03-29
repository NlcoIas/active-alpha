"""Shared FastAPI dependencies for the Active Alpha API."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import secrets

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.aggregator import HoldingsAggregator
from app.clients.fmp_client import FMPClient
from app.config import settings
from app.database import SessionLocal

# Singleton FMP client instance (kept for backwards compatibility)
_fmp_client: FMPClient | None = None

# Singleton aggregator instance (primary entry point for holdings data)
_aggregator: HoldingsAggregator | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with SessionLocal() as session:
        yield session


def get_aggregator() -> HoldingsAggregator:
    """Get the singleton holdings aggregator instance.

    The aggregator routes requests to free provider-specific clients first,
    falling back to FMP if an API key is configured.
    It must be closed on application shutdown via the lifespan handler.
    """
    global _aggregator  # noqa: PLW0603
    if _aggregator is None:
        # Only create FMP client if a real API key is configured
        fmp = None
        if settings.fmp_api_key and settings.fmp_api_key not in ("", "SET_ME", "your_fmp_api_key_here"):
            fmp = FMPClient(
                api_key=settings.fmp_api_key,
                base_url=settings.fmp_base_url,
                max_concurrent=settings.fmp_max_concurrent,
                requests_per_minute=settings.fmp_requests_per_minute,
            )
        _aggregator = HoldingsAggregator(fmp_client=fmp)
    return _aggregator


async def shutdown_aggregator() -> None:
    """Close the aggregator and all provider clients on application shutdown."""
    global _aggregator  # noqa: PLW0603
    if _aggregator is not None:
        await _aggregator.close()
        _aggregator = None


def get_fmp_client() -> FMPClient:
    """Get the singleton FMP client instance.

    DEPRECATED: Use get_aggregator() instead. Kept for backwards compatibility
    with code that needs direct FMP access (e.g. ETF list, stock prices).
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
    """Close the FMP client on application shutdown.

    DEPRECATED: Use shutdown_aggregator() instead.
    """
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
    if not secrets.compare_digest(x_api_key, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return x_api_key
