"""Fund endpoints: list and detail views."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.deviation import Deviation
from app.models.fund import Fund
from app.models.holdings_snapshot import HoldingsSnapshot
from app.schemas.common import CursorPagination
from app.schemas.fund import (
    FundDetailResponse,
    FundListResponse,
    FundResponse,
    TopDeviation,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["funds"])


def _decimal_to_str(val: Decimal | None) -> str | None:
    """Convert a Decimal to its string representation, preserving precision."""
    if val is None:
        return None
    return str(val)


def _fund_to_response(fund: Fund) -> FundResponse:
    """Map a Fund ORM object to the public FundResponse schema."""
    return FundResponse(
        id=fund.id,
        ticker=fund.ticker,
        name=fund.name,
        issuer=fund.issuer,
        type=fund.type,
        asset_class=fund.asset_class,
        benchmark=fund.benchmark if fund.benchmark else None,
        expense_ratio=_decimal_to_str(fund.expense_ratio),
        last_holdings_date=fund.last_holdings_date,
        data_quality=fund.data_quality,
        is_active=fund.is_active,
    )


@router.get("/", response_model=FundListResponse)
async def list_funds(
    is_active: bool | None = Query(None, description="Filter by active status"),
    benchmark_ticker: str | None = Query(None, description="Filter by benchmark ticker"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    cursor: str | None = Query(None, description="Cursor for pagination (fund ID)"),
    db: AsyncSession = Depends(get_db),
) -> FundListResponse:
    """List funds with optional filters and cursor-based pagination."""
    # Base query with eager-loaded benchmark
    query = (
        select(Fund)
        .options(joinedload(Fund.benchmark))
        .order_by(Fund.ticker)
    )

    # Apply filters
    if is_active is not None:
        query = query.where(Fund.is_active == is_active)
    if benchmark_ticker:
        from app.models.benchmark import Benchmark

        query = query.join(Fund.benchmark).where(Benchmark.ticker == benchmark_ticker)

    # Count total before pagination
    count_query = select(func.count()).select_from(Fund)
    if is_active is not None:
        count_query = count_query.where(Fund.is_active == is_active)
    if benchmark_ticker:
        from app.models.benchmark import Benchmark

        count_query = count_query.join(Fund.benchmark).where(
            Benchmark.ticker == benchmark_ticker
        )
    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()

    # Apply cursor
    if cursor:
        # Cursor is the last fund's ticker from the previous page
        query = query.where(Fund.ticker > cursor)

    # Fetch one extra to detect has_more
    query = query.limit(limit + 1)
    result = await db.execute(query)
    funds = list(result.scalars().unique().all())

    has_more = len(funds) > limit
    if has_more:
        funds = funds[:limit]

    next_cursor = funds[-1].ticker if has_more and funds else None

    return FundListResponse(
        data=[_fund_to_response(f) for f in funds],
        pagination=CursorPagination(
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        ),
    )


@router.get("/{ticker}", response_model=FundDetailResponse)
async def get_fund_detail(
    ticker: str,
    db: AsyncSession = Depends(get_db),
) -> FundDetailResponse:
    """Get detailed fund information including top deviations."""
    # Fetch fund with benchmark
    query = (
        select(Fund)
        .options(joinedload(Fund.benchmark))
        .where(Fund.ticker == ticker.upper())
    )
    result = await db.execute(query)
    fund = result.scalars().unique().one_or_none()

    if not fund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fund with ticker '{ticker.upper()}' not found.",
        )

    # Count holdings for the latest snapshot date
    holdings_count = 0
    if fund.last_holdings_date:
        count_query = (
            select(func.count())
            .select_from(HoldingsSnapshot)
            .where(
                HoldingsSnapshot.fund_id == fund.id,
                HoldingsSnapshot.snapshot_date == fund.last_holdings_date,
            )
        )
        count_result = await db.execute(count_query)
        holdings_count = count_result.scalar_one()

    # Fetch top 5 deviations (by absolute deviation, descending) for latest date
    top_deviations: list[TopDeviation] = []
    if fund.last_holdings_date:
        dev_query = (
            select(Deviation)
            .where(
                Deviation.fund_id == fund.id,
                Deviation.snapshot_date == fund.last_holdings_date,
            )
            .order_by(Deviation.abs_deviation_pct.desc())
            .limit(5)
        )
        dev_result = await db.execute(dev_query)
        deviations = dev_result.scalars().all()
        top_deviations = [
            TopDeviation(
                ticker=d.ticker,
                etf_weight_pct=str(d.etf_weight_pct) if d.etf_weight_pct is not None else "0",
                benchmark_weight_pct=str(d.benchmark_weight_pct) if d.benchmark_weight_pct is not None else "0",
                deviation_pct=str(d.deviation_pct),
                direction=d.direction,
            )
            for d in deviations
        ]

    return FundDetailResponse(
        id=fund.id,
        ticker=fund.ticker,
        name=fund.name,
        issuer=fund.issuer,
        type=fund.type,
        asset_class=fund.asset_class,
        benchmark=fund.benchmark if fund.benchmark else None,
        expense_ratio=_decimal_to_str(fund.expense_ratio),
        last_holdings_date=fund.last_holdings_date,
        data_quality=fund.data_quality,
        is_active=fund.is_active,
        inception_date=fund.inception_date,
        holdings_count=holdings_count,
        top_deviations=top_deviations,
    )
