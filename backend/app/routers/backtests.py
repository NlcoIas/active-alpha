"""Backtest endpoints: run custom backtests and retrieve pre-computed strategies."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.backtest import (
    BacktestConfigSchema,
    BacktestMetrics,
    BacktestResultSchema,
    PrecomputedStrategySchema,
)
from app.services.backtest_cache import BacktestCache
from app.services.backtest_engine import BacktestEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtests"])

# Singleton cache and engine
_cache = BacktestCache()
_engine = BacktestEngine()

# Simple in-memory rate limiter: 5 backtest runs per minute per IP
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60.0  # seconds
_RATE_LIMIT_MAX = 5  # requests per window


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if IP exceeds rate limit for backtest runs."""
    now = time.monotonic()
    timestamps = _rate_limit_store[client_ip]
    # Prune old entries
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before running another backtest.",
        )
    _rate_limit_store[client_ip].append(now)


# Pre-computed strategies: well-known configurations users can browse
PRECOMPUTED_STRATEGIES = [
    {
        "name": "Top 10 Overweights (Monthly, Equal)",
        "description": (
            "Monthly rebalance into the top 10 most overweighted stocks "
            "across all tracked active ETFs, equally weighted."
        ),
        "config": BacktestConfigSchema(
            benchmark_ticker="SPY",
            top_n=10,
            rebalance_frequency="monthly",
            holding_period_days=21,
            min_deviation_pct=0.5,
            weighting="equal",
            lookback_years=1,
            direction="long",
            transaction_cost_bps=10,
        ),
    },
    {
        "name": "Top 5 Conviction Picks (Weekly, Deviation-Weighted)",
        "description": (
            "Weekly rebalance into the top 5 overweighted stocks, "
            "weighted by their deviation magnitude."
        ),
        "config": BacktestConfigSchema(
            benchmark_ticker="SPY",
            top_n=5,
            rebalance_frequency="weekly",
            holding_period_days=5,
            min_deviation_pct=1.0,
            weighting="deviation_weighted",
            lookback_years=1,
            direction="long",
            transaction_cost_bps=10,
        ),
    },
    {
        "name": "Top 20 Broad Overweights (Monthly, Equal)",
        "description": (
            "Monthly rebalance into the top 20 overweighted stocks "
            "for broader diversification."
        ),
        "config": BacktestConfigSchema(
            benchmark_ticker="SPY",
            top_n=20,
            rebalance_frequency="monthly",
            holding_period_days=21,
            min_deviation_pct=0.3,
            weighting="equal",
            lookback_years=2,
            direction="long",
            transaction_cost_bps=10,
        ),
    },
]


@router.post("/run", response_model=BacktestResultSchema)
async def run_backtest(config: BacktestConfigSchema, request: Request) -> BacktestResultSchema:
    """Run a backtest with the given configuration.

    Checks Redis cache first. If cached result exists, returns it immediately.
    Otherwise, runs the backtest and caches the result.
    """
    # Rate limit check
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    config_dict = config.model_dump()

    # Check cache
    cached = await _cache.get(config_dict)
    if cached is not None:
        logger.info("Returning cached backtest result")
        result = BacktestResultSchema(**cached)
        result.cached = True
        return result

    # Run backtest
    try:
        result = await _engine.run_backtest(config)
    except Exception:
        logger.exception("Backtest execution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backtest computation failed. Please try again.",
        )

    # Cache result
    await _cache.set(config_dict, result.model_dump(mode="json"))

    return result


@router.get("/precomputed", response_model=list[PrecomputedStrategySchema])
async def list_precomputed_strategies() -> list[PrecomputedStrategySchema]:
    """List pre-computed backtest strategies that users can explore.

    These are well-known configurations with descriptive names.
    The actual backtest results are not included; call POST /run
    with the config to get results.
    """
    results: list[PrecomputedStrategySchema] = []
    for strategy in PRECOMPUTED_STRATEGIES:
        # Provide placeholder metrics (the UI will call /run to get actual results)
        results.append(
            PrecomputedStrategySchema(
                name=strategy["name"],
                description=strategy["description"],
                config=strategy["config"],
                metrics=BacktestMetrics(
                    cumulative_return=0.0,
                    annualized_return=0.0,
                    sharpe_ratio=0.0,
                    sortino_ratio=0.0,
                    max_drawdown=0.0,
                    hit_rate=0.0,
                    win_loss_ratio=0.0,
                    turnover=0.0,
                    total_trades=0,
                ),
            )
        )
    return results
