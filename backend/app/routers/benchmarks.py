"""Benchmark endpoints: list benchmarks and their holdings."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.benchmark import Benchmark
from app.models.benchmark_holding import BenchmarkHolding
from app.schemas.benchmark import (
    BenchmarkHoldingRecord,
    BenchmarkHoldingsResponse,
    BenchmarkResponse,
)
from app.schemas.common import CursorPagination

logger = logging.getLogger(__name__)

router = APIRouter(tags=["benchmarks"])


@router.get("/", response_model=list[BenchmarkResponse])
async def list_benchmarks(
    db: AsyncSession = Depends(get_db),
) -> list[BenchmarkResponse]:
    """List all tracked benchmarks."""
    query = select(Benchmark).order_by(Benchmark.ticker)
    result = await db.execute(query)
    benchmarks = result.scalars().all()
    return [BenchmarkResponse.model_validate(b) for b in benchmarks]


@router.get("/{ticker}/holdings", response_model=BenchmarkHoldingsResponse)
async def get_benchmark_holdings(
    ticker: str,
    date: date | None = Query(None, description="Snapshot date (YYYY-MM-DD). Defaults to latest."),
    limit: int = Query(100, ge=1, le=500, description="Maximum holdings to return"),
    cursor: str | None = Query(None, description="Cursor for pagination (holding ticker)"),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkHoldingsResponse:
    """Get benchmark holdings for a specific date (or latest available)."""
    # Resolve benchmark
    bench_query = select(Benchmark).where(Benchmark.ticker == ticker.upper())
    bench_result = await db.execute(bench_query)
    benchmark = bench_result.scalars().one_or_none()

    if not benchmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark with ticker '{ticker.upper()}' not found.",
        )

    # Determine snapshot date
    snapshot_date = date
    if snapshot_date is None:
        latest_query = (
            select(func.max(BenchmarkHolding.snapshot_date))
            .where(BenchmarkHolding.benchmark_id == benchmark.id)
        )
        latest_result = await db.execute(latest_query)
        snapshot_date = latest_result.scalar_one_or_none()

    if snapshot_date is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No holdings data found for benchmark '{ticker.upper()}'.",
        )

    # Base filter
    base_filter = (
        BenchmarkHolding.benchmark_id == benchmark.id,
        BenchmarkHolding.snapshot_date == snapshot_date,
    )

    # Total count
    count_query = select(func.count()).select_from(BenchmarkHolding).where(*base_filter)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    # Fetch holdings
    holdings_query = (
        select(BenchmarkHolding)
        .where(*base_filter)
        .order_by(BenchmarkHolding.weight_pct.desc(), BenchmarkHolding.ticker)
    )

    if cursor:
        holdings_query = holdings_query.where(BenchmarkHolding.ticker > cursor)

    holdings_query = holdings_query.limit(limit + 1)
    holdings_result = await db.execute(holdings_query)
    holdings = list(holdings_result.scalars().all())

    has_more = len(holdings) > limit
    if has_more:
        holdings = holdings[:limit]

    next_cursor = holdings[-1].ticker if has_more and holdings else None

    data = [
        BenchmarkHoldingRecord(
            ticker=h.ticker,
            name=h.name,
            weight_pct=str(h.weight_pct),
        )
        for h in holdings
    ]

    return BenchmarkHoldingsResponse(
        benchmark_ticker=benchmark.ticker,
        snapshot_date=snapshot_date,
        holdings_count=total_count,
        data=data,
        pagination=CursorPagination(
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        ),
    )
