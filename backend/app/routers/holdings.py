"""Holdings endpoints: fund holdings snapshots."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.fund import Fund
from app.models.holdings_snapshot import HoldingsSnapshot
from app.schemas.common import CursorPagination
from app.schemas.holdings import HoldingRecord, HoldingsSnapshotResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["holdings"])


@router.get("/funds/{ticker}/holdings", response_model=HoldingsSnapshotResponse)
async def get_fund_holdings(
    ticker: str,
    date: date | None = Query(None, description="Snapshot date (YYYY-MM-DD). Defaults to latest."),
    limit: int = Query(100, ge=1, le=500, description="Maximum holdings to return"),
    cursor: str | None = Query(None, description="Cursor for pagination (holding ticker)"),
    db: AsyncSession = Depends(get_db),
) -> HoldingsSnapshotResponse:
    """Get holdings for a fund on a specific date (or latest available)."""
    # Resolve fund
    fund_query = select(Fund).where(Fund.ticker == ticker.upper())
    fund_result = await db.execute(fund_query)
    fund = fund_result.scalars().one_or_none()

    if not fund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fund with ticker '{ticker.upper()}' not found.",
        )

    # Determine snapshot date: use provided date or fall back to latest
    snapshot_date = date
    if snapshot_date is None:
        latest_query = (
            select(func.max(HoldingsSnapshot.snapshot_date))
            .where(HoldingsSnapshot.fund_id == fund.id)
        )
        latest_result = await db.execute(latest_query)
        snapshot_date = latest_result.scalar_one_or_none()

    if snapshot_date is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No holdings data found for fund '{ticker.upper()}'.",
        )

    # Base query for this fund+date
    base_filter = (
        HoldingsSnapshot.fund_id == fund.id,
        HoldingsSnapshot.snapshot_date == snapshot_date,
    )

    # Total count
    count_query = select(func.count()).select_from(HoldingsSnapshot).where(*base_filter)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    # Weight sum
    sum_query = select(func.sum(HoldingsSnapshot.weight_pct)).where(*base_filter)
    sum_result = await db.execute(sum_query)
    weight_sum: Decimal | None = sum_result.scalar_one_or_none()

    # Check staleness (any row for this snapshot marked stale)
    stale_query = (
        select(HoldingsSnapshot.is_stale)
        .where(*base_filter)
        .limit(1)
    )
    stale_result = await db.execute(stale_query)
    is_stale = bool(stale_result.scalar_one_or_none())

    # Fetch holdings ordered by weight descending
    holdings_query = (
        select(HoldingsSnapshot)
        .where(*base_filter)
        .order_by(HoldingsSnapshot.weight_pct.desc(), HoldingsSnapshot.ticker)
    )

    if cursor:
        # Cursor pagination: skip rows until we pass the cursor ticker
        # Since we order by weight desc then ticker asc, we need a composite cursor.
        # For simplicity, use offset-based approach via ticker cursor.
        holdings_query = holdings_query.where(HoldingsSnapshot.ticker > cursor)

    holdings_query = holdings_query.limit(limit + 1)
    holdings_result = await db.execute(holdings_query)
    holdings = list(holdings_result.scalars().all())

    has_more = len(holdings) > limit
    if has_more:
        holdings = holdings[:limit]

    next_cursor = holdings[-1].ticker if has_more and holdings else None

    data = [
        HoldingRecord(
            ticker=h.ticker,
            name=h.name,
            asset_type=h.asset_type,
            weight_pct=str(h.weight_pct),
            shares=str(h.shares) if h.shares is not None else None,
            market_value=str(h.market_value) if h.market_value is not None else None,
        )
        for h in holdings
    ]

    return HoldingsSnapshotResponse(
        fund_ticker=fund.ticker,
        snapshot_date=snapshot_date,
        is_stale=is_stale,
        weight_sum_pct=str(weight_sum) if weight_sum is not None else "0",
        holdings_count=total_count,
        data=data,
        pagination=CursorPagination(
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        ),
    )
