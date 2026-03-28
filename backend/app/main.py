"""FastAPI application factory for Active Alpha.

Creates the app with:
- CORS middleware
- Lifespan handler (FMP client init/teardown, optional scheduler)
- Global exception handler returning ErrorResponse format
- All routers registered under /api/v1 (except health probes)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.dependencies import get_fmp_client, shutdown_fmp_client
from app.routers.benchmarks import router as benchmarks_router
from app.routers.deviations import router as deviations_router
from app.routers.funds import router as funds_router
from app.routers.health import router as health_router
from app.routers.holdings import router as holdings_router
from app.routers.pipeline import router as pipeline_router

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup and shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle resources.

    Startup:
      - Initialise the singleton FMP client
      - Start the APScheduler (only outside of test environments)

    Shutdown:
      - Stop the scheduler gracefully
      - Close the FMP client HTTP connection pool
    """
    # --- Startup ---
    logger.info("Active Alpha API starting up (env=%s)", settings.environment)

    # Eagerly create the FMP client so it is ready for requests
    get_fmp_client()

    # Start scheduler in non-test environments
    if settings.environment != "test":
        try:
            from app.scheduler.jobs import start_scheduler

            start_scheduler(app)
        except Exception:
            logger.exception("Failed to start scheduler; continuing without it")

    yield

    # --- Shutdown ---
    logger.info("Active Alpha API shutting down")

    try:
        from app.scheduler.jobs import stop_scheduler

        stop_scheduler()
    except Exception:
        logger.exception("Error stopping scheduler")

    await shutdown_fmp_client()

    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="Active ETF Deviation Tracker & Backtesting Platform",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://alpha.nicolasschaerer.ch",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Exception handlers ---
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Return all HTTP errors in the standard ErrorResponse shape."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "code": f"HTTP_{exc.status_code}",
                "details": None,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions. Never expose internals."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "details": None,
            },
        )

    # --- Routers ---
    # Health probes at root level (no /api/v1 prefix)
    app.include_router(health_router)

    # API v1 endpoints
    app.include_router(funds_router, prefix="/api/v1/funds", tags=["funds"])
    app.include_router(holdings_router, prefix="/api/v1", tags=["holdings"])
    app.include_router(deviations_router, prefix="/api/v1", tags=["deviations"])
    app.include_router(benchmarks_router, prefix="/api/v1/benchmarks", tags=["benchmarks"])
    app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["pipeline"])

    return app


# Module-level app instance for uvicorn (e.g. `uvicorn app.main:app`)
app = create_app()
