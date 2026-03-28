"""Deviation endpoints: fund-vs-benchmark deviations and cross-fund stock holders."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.benchmark import Benchmark
from app.models.deviation import Deviation
from app.models.fund import Fund
from app.schemas.common import CursorPagination
from app.schemas.deviation import (
    DeviationHistoryRecord,
    DeviationHistoryResponse,
    DeviationRecord,
    DeviationResponse,
    StockHolderRecord,
    StockHoldersResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deviations"])


# ---------------------------------------------------------------------------
# Fund-level deviations
# ---------------------------------------------------------------------------


@router.get("/funds/{ticker}/deviations", response_model=DeviationResponse)
async def get_fund_deviations(
    ticker: str,
    date: date | None = Query(None, description="Snapshot date (YYYY-MM-DD). Defaults to latest."),
    direction: str | None = Query(
        None,
        description="Filter direction: overweight, underweight, etf_only, benchmark_only",
    ),
    min_abs_deviation: float | None = Query(
        None, ge=0, description="Minimum absolute deviation percentage"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    cursor: str | None = Query(None, description="Cursor for pagination (deviation ticker)"),
    db: AsyncSession = Depends(get_db),
) -> DeviationResponse:
    """Get deviations for a fund against its benchmark on a given date."""
    # Resolve fund
    fund_query = (
        select(Fund)
        .where(Fund.ticker == ticker.upper())
    )
    fund_result = await db.execute(fund_query)
    fund = fund_result.scalars().one_or_none()

    if not fund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fund with ticker '{ticker.upper()}' not found.",
        )

    if not fund.benchmark_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fund '{ticker.upper()}' has no assigned benchmark.",
        )

    # Resolve benchmark ticker for the response
    bench_query = select(Benchmark).where(Benchmark.id == fund.benchmark_id)
    bench_result = await db.execute(bench_query)
    benchmark = bench_result.scalars().one_or_none()
    benchmark_ticker = benchmark.ticker if benchmark else "UNKNOWN"

    # Determine snapshot date
    snapshot_date = date
    if snapshot_date is None:
        latest_query = (
            select(func.max(Deviation.snapshot_date))
            .where(Deviation.fund_id == fund.id)
        )
        latest_result = await db.execute(latest_query)
        snapshot_date = latest_result.scalar_one_or_none()

    if snapshot_date is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No deviation data found for fund '{ticker.upper()}'.",
        )

    # Build query
    base_filter = [
        Deviation.fund_id == fund.id,
        Deviation.snapshot_date == snapshot_date,
    ]

    if direction:
        allowed_directions = {"overweight", "underweight", "etf_only", "benchmark_only"}
        if direction not in allowed_directions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid direction. Must be one of: {', '.join(sorted(allowed_directions))}",
            )
        base_filter.append(Deviation.direction == direction)

    if min_abs_deviation is not None:
        base_filter.append(Deviation.abs_deviation_pct >= min_abs_deviation)

    # Count total matching
    count_query = select(func.count()).select_from(Deviation).where(*base_filter)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    # Fetch deviations ordered by absolute deviation descending
    dev_query = (
        select(Deviation)
        .where(*base_filter)
        .order_by(Deviation.abs_deviation_pct.desc(), Deviation.ticker)
    )

    if cursor:
        dev_query = dev_query.where(Deviation.ticker > cursor)

    dev_query = dev_query.limit(limit + 1)
    dev_result = await db.execute(dev_query)
    deviations = list(dev_result.scalars().all())

    has_more = len(deviations) > limit
    if has_more:
        deviations = deviations[:limit]

    next_cursor = deviations[-1].ticker if has_more and deviations else None

    data = [
        DeviationRecord(
            ticker=d.ticker,
            etf_weight_pct=str(d.etf_weight_pct) if d.etf_weight_pct is not None else "0",
            benchmark_weight_pct=str(d.benchmark_weight_pct) if d.benchmark_weight_pct is not None else "0",
            deviation_pct=str(d.deviation_pct),
            abs_deviation_pct=str(d.abs_deviation_pct),
            direction=d.direction,
        )
        for d in deviations
    ]

    return DeviationResponse(
        fund_ticker=fund.ticker,
        benchmark_ticker=benchmark_ticker,
        snapshot_date=snapshot_date,
        data=data,
        pagination=CursorPagination(
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        ),
    )


# ---------------------------------------------------------------------------
# Deviation history for a specific stock within a fund
# ---------------------------------------------------------------------------


@router.get(
    "/funds/{ticker}/deviations/history",
    response_model=DeviationHistoryResponse,
)
async def get_deviation_history(
    ticker: str,
    stock_ticker: str = Query(..., description="Stock ticker to track over time"),
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> DeviationHistoryResponse:
    """Get the deviation time series for a specific stock within a fund."""
    # Resolve fund
    fund_query = select(Fund).where(Fund.ticker == ticker.upper())
    fund_result = await db.execute(fund_query)
    fund = fund_result.scalars().one_or_none()

    if not fund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fund with ticker '{ticker.upper()}' not found.",
        )

    # Build query
    filters = [
        Deviation.fund_id == fund.id,
        Deviation.ticker == stock_ticker.upper(),
    ]
    if start_date:
        filters.append(Deviation.snapshot_date >= start_date)
    if end_date:
        filters.append(Deviation.snapshot_date <= end_date)

    query = (
        select(Deviation)
        .where(*filters)
        .order_by(Deviation.snapshot_date.asc())
    )
    result = await db.execute(query)
    deviations = result.scalars().all()

    data = [
        DeviationHistoryRecord(
            snapshot_date=d.snapshot_date,
            etf_weight_pct=str(d.etf_weight_pct) if d.etf_weight_pct is not None else "0",
            benchmark_weight_pct=str(d.benchmark_weight_pct) if d.benchmark_weight_pct is not None else "0",
            deviation_pct=str(d.deviation_pct),
            direction=d.direction,
        )
        for d in deviations
    ]

    return DeviationHistoryResponse(
        fund_ticker=fund.ticker,
        stock_ticker=stock_ticker.upper(),
        data=data,
    )


# ---------------------------------------------------------------------------
# Cross-fund: which ETFs hold a given stock
# ---------------------------------------------------------------------------


@router.get("/stocks/{ticker}/holders", response_model=StockHoldersResponse)
async def get_stock_holders(
    ticker: str,
    date: date | None = Query(None, description="Snapshot date (YYYY-MM-DD). Defaults to latest."),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    cursor: str | None = Query(None, description="Cursor for pagination (fund ticker)"),
    db: AsyncSession = Depends(get_db),
) -> StockHoldersResponse:
    """Find all ETFs that hold a given stock, with their deviation data."""
    stock_ticker_upper = ticker.upper()

    # Determine snapshot date
    snapshot_date = date
    if snapshot_date is None:
        latest_query = (
            select(func.max(Deviation.snapshot_date))
            .where(Deviation.ticker == stock_ticker_upper)
        )
        latest_result = await db.execute(latest_query)
        snapshot_date = latest_result.scalar_one_or_none()

    if snapshot_date is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No deviation data found for stock '{stock_ticker_upper}'.",
        )

    # Count total holders
    base_filter = [
        Deviation.ticker == stock_ticker_upper,
        Deviation.snapshot_date == snapshot_date,
    ]
    count_query = select(func.count()).select_from(Deviation).where(*base_filter)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    # Fetch deviations joined with fund info
    holders_query = (
        select(Deviation, Fund.ticker.label("fund_ticker_col"), Fund.name.label("fund_name_col"))
        .join(Fund, Deviation.fund_id == Fund.id)
        .where(*base_filter)
        .order_by(Deviation.abs_deviation_pct.desc(), Fund.ticker)
    )

    if cursor:
        holders_query = holders_query.where(Fund.ticker > cursor)

    holders_query = holders_query.limit(limit + 1)
    holders_result = await db.execute(holders_query)
    rows = list(holders_result.all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor = rows[-1].fund_ticker_col if has_more and rows else None

    data = [
        StockHolderRecord(
            fund_ticker=row.fund_ticker_col,
            fund_name=row.fund_name_col,
            etf_weight_pct=str(row.Deviation.etf_weight_pct) if row.Deviation.etf_weight_pct is not None else "0",
            benchmark_weight_pct=(
                str(row.Deviation.benchmark_weight_pct)
                if row.Deviation.benchmark_weight_pct is not None
                else "0"
            ),
            deviation_pct=str(row.Deviation.deviation_pct),
            direction=row.Deviation.direction,
        )
        for row in rows
    ]

    return StockHoldersResponse(
        stock_ticker=stock_ticker_upper,
        snapshot_date=snapshot_date,
        data=data,
        pagination=CursorPagination(
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        ),
    )
