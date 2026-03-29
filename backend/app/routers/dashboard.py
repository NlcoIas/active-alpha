"""Dashboard endpoint: aggregated summary data for the home page."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.deviation import Deviation
from app.models.fund import Fund
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


# ---------------------------------------------------------------------------
# Response schemas (local to this router for simplicity)
# ---------------------------------------------------------------------------


class TopOverweightRecord(BaseModel):
    """A top overweight stock across all funds."""

    ticker: str
    fund_ticker: str
    fund_name: str
    deviation_pct: float
    etf_weight_pct: float | None
    benchmark_weight_pct: float | None


class ConsensusPickRecord(BaseModel):
    """A stock overweighted by multiple funds."""

    ticker: str
    fund_count: int
    avg_deviation_pct: float
    max_deviation_pct: float
    fund_tickers: list[str]


class DashboardStats(BaseModel):
    """Summary statistics for the dashboard."""

    total_funds: int
    funds_with_data: int
    latest_date: date | None
    total_deviations: int


class DashboardResponse(BaseModel):
    """Full dashboard summary response."""

    stats: DashboardStats
    top_overweights: list[TopOverweightRecord]
    consensus_picks: list[ConsensusPickRecord]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=DashboardResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Get aggregated dashboard data for the home page.

    Returns:
    - Top 20 overweights across all funds
    - Consensus picks (stocks overweighted by 3+ funds)
    - Summary stats
    """
    # --- Stats ---
    total_funds_result = await db.execute(
        select(func.count()).select_from(Fund).where(Fund.is_active.is_(True))
    )
    total_funds = total_funds_result.scalar_one()

    funds_with_data_result = await db.execute(
        select(func.count()).select_from(Fund).where(
            Fund.is_active.is_(True),
            Fund.last_holdings_date.isnot(None),
        )
    )
    funds_with_data = funds_with_data_result.scalar_one()

    latest_date_result = await db.execute(
        select(func.max(Deviation.snapshot_date))
    )
    latest_date = latest_date_result.scalar_one_or_none()

    total_devs_result = await db.execute(
        select(func.count()).select_from(Deviation).where(
            Deviation.snapshot_date == latest_date
        ) if latest_date else select(func.count()).select_from(Deviation)
    )
    total_deviations = total_devs_result.scalar_one()

    stats = DashboardStats(
        total_funds=total_funds,
        funds_with_data=funds_with_data,
        latest_date=latest_date,
        total_deviations=total_deviations,
    )

    if latest_date is None:
        return DashboardResponse(
            stats=stats,
            top_overweights=[],
            consensus_picks=[],
        )

    # --- Top 20 overweights ---
    top_query = (
        select(
            Deviation,
            Fund.ticker.label("fund_ticker"),
            Fund.name.label("fund_name"),
        )
        .join(Fund, Deviation.fund_id == Fund.id)
        .where(
            Deviation.snapshot_date == latest_date,
            Deviation.direction == "overweight",
        )
        .order_by(Deviation.abs_deviation_pct.desc())
        .limit(20)
    )
    top_result = await db.execute(top_query)
    top_rows = top_result.all()

    top_overweights = [
        TopOverweightRecord(
            ticker=row.Deviation.ticker,
            fund_ticker=row.fund_ticker,
            fund_name=row.fund_name,
            deviation_pct=float(row.Deviation.deviation_pct),
            etf_weight_pct=(
                float(row.Deviation.etf_weight_pct)
                if row.Deviation.etf_weight_pct is not None
                else None
            ),
            benchmark_weight_pct=(
                float(row.Deviation.benchmark_weight_pct)
                if row.Deviation.benchmark_weight_pct is not None
                else None
            ),
        )
        for row in top_rows
    ]

    # --- Consensus picks (3+ funds overweight the same stock) ---
    consensus_query = text("""
        SELECT
            d.ticker,
            COUNT(DISTINCT f.id) AS fund_count,
            AVG(d.deviation_pct) AS avg_deviation_pct,
            MAX(d.deviation_pct) AS max_deviation_pct,
            ARRAY_AGG(DISTINCT f.ticker ORDER BY f.ticker) AS fund_tickers
        FROM deviations d
        JOIN funds f ON d.fund_id = f.id
        WHERE d.snapshot_date = :latest_date
          AND d.direction = 'overweight'
        GROUP BY d.ticker
        HAVING COUNT(DISTINCT f.id) >= 3
        ORDER BY COUNT(DISTINCT f.id) DESC, AVG(d.deviation_pct) DESC
        LIMIT 50
    """)
    consensus_result = await db.execute(consensus_query, {"latest_date": latest_date})
    consensus_rows = consensus_result.fetchall()

    consensus_picks = [
        ConsensusPickRecord(
            ticker=row.ticker,
            fund_count=row.fund_count,
            avg_deviation_pct=round(float(row.avg_deviation_pct), 5),
            max_deviation_pct=round(float(row.max_deviation_pct), 5),
            fund_tickers=list(row.fund_tickers),
        )
        for row in consensus_rows
    ]

    return DashboardResponse(
        stats=stats,
        top_overweights=top_overweights,
        consensus_picks=consensus_picks,
    )
