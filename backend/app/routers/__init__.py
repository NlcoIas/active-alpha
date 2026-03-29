"""FastAPI routers for the Active Alpha API."""

from app.routers.backtests import router as backtests_router
from app.routers.benchmarks import router as benchmarks_router
from app.routers.dashboard import router as dashboard_router
from app.routers.deviations import router as deviations_router
from app.routers.funds import router as funds_router
from app.routers.health import router as health_router
from app.routers.holdings import router as holdings_router
from app.routers.pipeline import router as pipeline_router

__all__ = [
    "backtests_router",
    "benchmarks_router",
    "dashboard_router",
    "deviations_router",
    "funds_router",
    "health_router",
    "holdings_router",
    "pipeline_router",
]
