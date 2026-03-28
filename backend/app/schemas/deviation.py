"""Deviation-related Pydantic schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.common import CursorPagination


class DeviationRecord(BaseModel):
    """A single deviation entry (ETF weight vs benchmark weight for one stock)."""

    ticker: str
    etf_weight_pct: str
    benchmark_weight_pct: str
    deviation_pct: str
    abs_deviation_pct: str
    direction: str


class DeviationResponse(BaseModel):
    """Paginated list of deviations for a fund/benchmark pair on a date."""

    fund_ticker: str
    benchmark_ticker: str
    snapshot_date: date
    data: list[DeviationRecord]
    pagination: CursorPagination


class DeviationHistoryRecord(BaseModel):
    """A single point in a stock's deviation history within a fund."""

    snapshot_date: date
    etf_weight_pct: str
    benchmark_weight_pct: str
    deviation_pct: str
    direction: str


class DeviationHistoryResponse(BaseModel):
    """Time series of deviations for a specific stock within a fund."""

    fund_ticker: str
    stock_ticker: str
    data: list[DeviationHistoryRecord]


class StockHolderRecord(BaseModel):
    """Which ETFs hold a given stock and by how much they deviate."""

    fund_ticker: str
    fund_name: str
    etf_weight_pct: str
    benchmark_weight_pct: str
    deviation_pct: str
    direction: str


class StockHoldersResponse(BaseModel):
    """Cross-fund view: all ETFs holding a specific stock."""

    stock_ticker: str
    snapshot_date: date
    data: list[StockHolderRecord]
    pagination: CursorPagination
