"""Benchmark-related Pydantic schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.common import CursorPagination


class BenchmarkResponse(BaseModel):
    """Public representation of a benchmark."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    ticker: str
    name: str
    index_name: str | None = None
    constituent_count: int | None = None
    last_holdings_date: date | None = None
    is_active: bool


class BenchmarkHoldingRecord(BaseModel):
    """A single holding within a benchmark snapshot."""

    ticker: str
    name: str | None = None
    weight_pct: str


class BenchmarkHoldingsResponse(BaseModel):
    """Benchmark holdings for a specific date."""

    benchmark_ticker: str
    snapshot_date: date
    holdings_count: int
    data: list[BenchmarkHoldingRecord]
    pagination: CursorPagination
