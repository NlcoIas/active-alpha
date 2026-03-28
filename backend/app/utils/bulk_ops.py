"""Raw SQL bulk upsert operations for pipeline writes.

Uses ON CONFLICT DO UPDATE for idempotent inserts.
Bypasses ORM intentionally for 10-50x performance on bulk writes.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.base import generate_cuid


async def bulk_upsert_holdings(
    conn: AsyncConnection,
    fund_id: str,
    target_date: date,
    rows: list[dict],
) -> int:
    """Upsert holdings for a fund on a date.

    Each row: {ticker, name, asset_type, weight_pct, shares, market_value, is_stale, source, fetched_at}
    Returns number of rows upserted.
    """
    if not rows:
        return 0

    stmt = text("""
        INSERT INTO holdings_snapshots
            (id, fund_id, snapshot_date, ticker, name, asset_type,
             weight_pct, shares, market_value, is_stale, source, fetched_at)
        VALUES
            (:id, :fund_id, :snapshot_date, :ticker, :name, :asset_type,
             :weight_pct, :shares, :market_value, :is_stale, :source, :fetched_at)
        ON CONFLICT (fund_id, snapshot_date, ticker) DO UPDATE SET
            name = EXCLUDED.name,
            asset_type = EXCLUDED.asset_type,
            weight_pct = EXCLUDED.weight_pct,
            shares = EXCLUDED.shares,
            market_value = EXCLUDED.market_value,
            is_stale = EXCLUDED.is_stale,
            fetched_at = EXCLUDED.fetched_at
    """)

    params = [
        {
            "id": generate_cuid(),
            "fund_id": fund_id,
            "snapshot_date": target_date,
            "ticker": row["ticker"],
            "name": row.get("name"),
            "asset_type": row.get("asset_type", "equity"),
            "weight_pct": row["weight_pct"],
            "shares": row.get("shares"),
            "market_value": row.get("market_value"),
            "is_stale": row.get("is_stale", False),
            "source": row.get("source", "fmp"),
            "fetched_at": row["fetched_at"],
        }
        for row in rows
    ]

    await conn.execute(stmt, params)
    return len(rows)


async def bulk_upsert_benchmark_holdings(
    conn: AsyncConnection,
    benchmark_id: str,
    target_date: date,
    rows: list[dict],
) -> int:
    """Upsert benchmark holdings for a benchmark on a date.

    Each row: {ticker, name, weight_pct, source, fetched_at}
    Returns number of rows upserted.
    """
    if not rows:
        return 0

    stmt = text("""
        INSERT INTO benchmark_holdings
            (id, benchmark_id, snapshot_date, ticker, name, weight_pct, source, fetched_at)
        VALUES
            (:id, :benchmark_id, :snapshot_date, :ticker, :name, :weight_pct, :source, :fetched_at)
        ON CONFLICT (benchmark_id, snapshot_date, ticker) DO UPDATE SET
            name = EXCLUDED.name,
            weight_pct = EXCLUDED.weight_pct,
            fetched_at = EXCLUDED.fetched_at
    """)

    params = [
        {
            "id": generate_cuid(),
            "benchmark_id": benchmark_id,
            "snapshot_date": target_date,
            "ticker": row["ticker"],
            "name": row.get("name"),
            "weight_pct": row["weight_pct"],
            "source": row.get("source", "fmp"),
            "fetched_at": row["fetched_at"],
        }
        for row in rows
    ]

    await conn.execute(stmt, params)
    return len(rows)


async def bulk_upsert_deviations(
    conn: AsyncConnection,
    rows: list[dict],
) -> int:
    """Upsert deviation records.

    Each row: {fund_id, benchmark_id, snapshot_date, ticker, etf_weight_pct,
               benchmark_weight_pct, deviation_pct, abs_deviation_pct, deviation_rank, direction}
    Returns number of rows upserted.
    """
    if not rows:
        return 0

    stmt = text("""
        INSERT INTO deviations
            (id, fund_id, benchmark_id, snapshot_date, ticker,
             etf_weight_pct, benchmark_weight_pct, deviation_pct,
             abs_deviation_pct, deviation_rank, direction)
        VALUES
            (:id, :fund_id, :benchmark_id, :snapshot_date, :ticker,
             :etf_weight_pct, :benchmark_weight_pct, :deviation_pct,
             :abs_deviation_pct, :deviation_rank, :direction)
        ON CONFLICT (fund_id, benchmark_id, snapshot_date, ticker) DO UPDATE SET
            etf_weight_pct = EXCLUDED.etf_weight_pct,
            benchmark_weight_pct = EXCLUDED.benchmark_weight_pct,
            deviation_pct = EXCLUDED.deviation_pct,
            abs_deviation_pct = EXCLUDED.abs_deviation_pct,
            deviation_rank = EXCLUDED.deviation_rank,
            direction = EXCLUDED.direction
    """)

    params = [
        {
            "id": generate_cuid(),
            "fund_id": row["fund_id"],
            "benchmark_id": row["benchmark_id"],
            "snapshot_date": row["snapshot_date"],
            "ticker": row["ticker"],
            "etf_weight_pct": row.get("etf_weight_pct"),
            "benchmark_weight_pct": row.get("benchmark_weight_pct"),
            "deviation_pct": row["deviation_pct"],
            "abs_deviation_pct": row["abs_deviation_pct"],
            "deviation_rank": row.get("deviation_rank"),
            "direction": row["direction"],
        }
        for row in rows
    ]

    await conn.execute(stmt, params)
    return len(rows)
