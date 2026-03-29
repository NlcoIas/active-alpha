"""Backtest-related Pydantic schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BacktestConfigSchema(BaseModel):
    """Request body for running a backtest."""

    benchmark_ticker: str = Field(
        default="SPY", description="Benchmark ticker to compare against"
    )
    fund_tickers: list[str] | None = Field(
        default=None,
        description="Specific fund tickers to include (None = all funds)",
    )
    top_n: int = Field(
        default=10, ge=1, le=20, description="Number of top overweight stocks to pick"
    )
    rebalance_frequency: Literal["daily", "weekly", "monthly"] = Field(
        default="monthly", description="How often to rebalance the portfolio"
    )
    holding_period_days: int = Field(
        default=21, ge=1, le=252, description="Days to hold positions before rebalance"
    )
    min_deviation_pct: float = Field(
        default=0.5, ge=0.0, description="Minimum deviation threshold (pct)"
    )
    weighting: Literal["equal", "deviation_weighted"] = Field(
        default="equal", description="How to weight positions"
    )
    lookback_years: int = Field(
        default=1, ge=1, le=5, description="Years of historical data to use"
    )
    direction: Literal["long", "short", "long_short"] = Field(
        default="long", description="Trade direction"
    )
    transaction_cost_bps: int = Field(
        default=10, ge=0, le=100, description="Transaction cost in basis points per trade"
    )


class EquityCurvePoint(BaseModel):
    """A single point on the equity curve."""

    date: date
    value: float
    benchmark_value: float


class MonthlyReturn(BaseModel):
    """Monthly return entry."""

    year: int
    month: int
    return_pct: float


class BacktestMetrics(BaseModel):
    """Computed performance metrics for a backtest."""

    cumulative_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    hit_rate: float
    win_loss_ratio: float
    turnover: float
    total_trades: int


class BacktestResultSchema(BaseModel):
    """Full backtest result response."""

    model_config = ConfigDict(from_attributes=True)

    config: BacktestConfigSchema
    metrics: BacktestMetrics
    equity_curve: list[EquityCurvePoint]
    monthly_returns: list[MonthlyReturn]
    cached: bool = False


class PrecomputedStrategySchema(BaseModel):
    """Summary of a pre-computed backtest strategy."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    config: BacktestConfigSchema
    metrics: BacktestMetrics
