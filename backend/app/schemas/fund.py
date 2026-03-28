"""Fund-related Pydantic schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.common import CursorPagination


class BenchmarkShort(BaseModel):
    """Minimal benchmark info embedded in fund responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    ticker: str
    name: str


class FundResponse(BaseModel):
    """Public representation of a fund."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    ticker: str
    name: str
    issuer: str | None = None
    type: str
    asset_class: str
    benchmark: BenchmarkShort | None = None
    expense_ratio: str | None = None
    last_holdings_date: date | None = None
    data_quality: str
    is_active: bool


class FundDetailResponse(FundResponse):
    """Extended fund info with inception date, holdings count, and top deviations."""

    inception_date: date | None = None
    holdings_count: int = 0
    top_deviations: list[TopDeviation] = []


class TopDeviation(BaseModel):
    """A single deviation entry for the fund detail view."""

    ticker: str
    etf_weight_pct: str
    benchmark_weight_pct: str
    deviation_pct: str
    direction: str


class FundListResponse(BaseModel):
    """Paginated list of funds."""

    data: list[FundResponse]
    pagination: CursorPagination


# Rebuild FundDetailResponse now that TopDeviation is defined
FundDetailResponse.model_rebuild()
