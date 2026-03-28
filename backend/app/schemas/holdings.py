"""Holdings-related Pydantic schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.common import CursorPagination


class HoldingRecord(BaseModel):
    """A single holding within a snapshot."""

    ticker: str
    name: str | None = None
    asset_type: str
    weight_pct: str
    shares: str | None = None
    market_value: str | None = None


class HoldingsSnapshotResponse(BaseModel):
    """Fund holdings for a specific date."""

    fund_ticker: str
    snapshot_date: date
    is_stale: bool
    weight_sum_pct: str
    holdings_count: int
    data: list[HoldingRecord]
    pagination: CursorPagination
