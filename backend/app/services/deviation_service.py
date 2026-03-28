"""Service for calculating weight deviations between ETF and benchmark holdings."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models import Benchmark, Deviation, Fund
from app.utils.bulk_ops import bulk_upsert_deviations

logger = logging.getLogger(__name__)


class DeviationService:
    """Calculates and queries deviations between fund and benchmark holdings."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def calculate_deviations(
        self,
        fund_id: str,
        benchmark_id: str,
        target_date: date,
    ) -> int:
        """Calculate deviations between a fund and its benchmark on a given date.

        Uses a FULL OUTER JOIN between holdings_snapshots and benchmark_holdings
        on (ticker, date). Classifies direction and ranks by absolute deviation.

        Returns the number of deviation rows upserted.
        """
        logger.info(
            "Calculating deviations for fund_id=%s vs benchmark_id=%s on %s",
            fund_id, benchmark_id, target_date,
        )

        # Full outer join between fund holdings and benchmark holdings
        join_query = text("""
            SELECT
                COALESCE(h.ticker, b.ticker) AS ticker,
                h.weight_pct AS etf_weight_pct,
                b.weight_pct AS benchmark_weight_pct,
                COALESCE(h.weight_pct, 0) - COALESCE(b.weight_pct, 0) AS deviation_pct,
                ABS(COALESCE(h.weight_pct, 0) - COALESCE(b.weight_pct, 0)) AS abs_deviation_pct,
                CASE
                    WHEN h.ticker IS NULL THEN 'benchmark_only'
                    WHEN b.ticker IS NULL THEN 'etf_only'
                    WHEN COALESCE(h.weight_pct, 0) - COALESCE(b.weight_pct, 0) > 0 THEN 'overweight'
                    WHEN COALESCE(h.weight_pct, 0) - COALESCE(b.weight_pct, 0) < 0 THEN 'underweight'
                    ELSE 'match'
                END AS direction,
                ROW_NUMBER() OVER (
                    ORDER BY ABS(COALESCE(h.weight_pct, 0) - COALESCE(b.weight_pct, 0)) DESC
                ) AS deviation_rank
            FROM holdings_snapshots h
            FULL OUTER JOIN benchmark_holdings b
                ON h.ticker = b.ticker
                AND b.benchmark_id = :benchmark_id
                AND b.snapshot_date = :target_date
            WHERE h.fund_id = :fund_id
              AND h.snapshot_date = :target_date

            UNION ALL

            -- Benchmark-only holdings (not in the fund)
            SELECT
                b.ticker AS ticker,
                NULL AS etf_weight_pct,
                b.weight_pct AS benchmark_weight_pct,
                0 - b.weight_pct AS deviation_pct,
                ABS(b.weight_pct) AS abs_deviation_pct,
                'benchmark_only' AS direction,
                0 AS deviation_rank
            FROM benchmark_holdings b
            WHERE b.benchmark_id = :benchmark_id
              AND b.snapshot_date = :target_date
              AND NOT EXISTS (
                  SELECT 1 FROM holdings_snapshots h
                  WHERE h.fund_id = :fund_id
                    AND h.snapshot_date = :target_date
                    AND h.ticker = b.ticker
              )
        """)

        async with engine.connect() as conn:
            result = await conn.execute(
                join_query,
                {
                    "fund_id": fund_id,
                    "benchmark_id": benchmark_id,
                    "target_date": target_date,
                },
            )
            rows = result.fetchall()

        if not rows:
            logger.warning(
                "No holdings found for deviation calculation: "
                "fund_id=%s, benchmark_id=%s, date=%s",
                fund_id, benchmark_id, target_date,
            )
            return 0

        # Build deviation records, re-rank after combining both parts
        combined = []
        for row in rows:
            combined.append({
                "ticker": row.ticker,
                "etf_weight_pct": float(row.etf_weight_pct) if row.etf_weight_pct is not None else None,
                "benchmark_weight_pct": float(row.benchmark_weight_pct) if row.benchmark_weight_pct is not None else None,
                "deviation_pct": float(row.deviation_pct),
                "abs_deviation_pct": float(row.abs_deviation_pct),
                "direction": row.direction,
            })

        # Deduplicate by ticker (the UNION ALL may produce duplicates for benchmark-only
        # rows when the FULL OUTER JOIN already matched them)
        seen_tickers: set[str] = set()
        deduped: list[dict] = []
        for item in combined:
            if item["ticker"] not in seen_tickers:
                seen_tickers.add(item["ticker"])
                deduped.append(item)

        # Re-rank by absolute deviation descending
        deduped.sort(key=lambda x: x["abs_deviation_pct"], reverse=True)
        deviation_rows: list[dict] = []
        for rank, item in enumerate(deduped, start=1):
            deviation_rows.append({
                "fund_id": fund_id,
                "benchmark_id": benchmark_id,
                "snapshot_date": target_date,
                "ticker": item["ticker"],
                "etf_weight_pct": item["etf_weight_pct"],
                "benchmark_weight_pct": item["benchmark_weight_pct"],
                "deviation_pct": item["deviation_pct"],
                "abs_deviation_pct": item["abs_deviation_pct"],
                "deviation_rank": rank,
                "direction": item["direction"],
            })

        # Bulk upsert via raw connection
        async with engine.connect() as conn:
            count = await bulk_upsert_deviations(conn, deviation_rows)
            await conn.commit()

        logger.info(
            "Stored %d deviations for fund_id=%s vs benchmark_id=%s on %s",
            count, fund_id, benchmark_id, target_date,
        )
        return count

    async def calculate_all_deviations(self, target_date: date) -> int:
        """Calculate deviations for all active funds that have a benchmark assigned.

        Returns total number of deviation rows upserted across all funds.
        """
        result = await self._db.execute(
            select(Fund).where(
                Fund.is_active.is_(True),
                Fund.benchmark_id.isnot(None),
            )
        )
        funds = result.scalars().all()

        if not funds:
            logger.warning("No active funds with benchmarks found")
            return 0

        total = 0
        for fund in funds:
            try:
                count = await self.calculate_deviations(
                    fund.id, fund.benchmark_id, target_date,
                )
                total += count
            except Exception as exc:
                logger.error(
                    "Failed to calculate deviations for fund %s: %s",
                    fund.ticker, exc,
                )
                # Per-fund failures are logged and skipped
                continue

        logger.info(
            "Calculated deviations for %d funds: %d total rows on %s",
            len(funds), total, target_date,
        )
        return total

    async def get_fund_deviations(
        self,
        fund_ticker: str,
        target_date: date | None = None,
        limit: int = 100,
        direction: str | None = None,
    ) -> list[dict]:
        """Query deviations for a specific fund.

        If target_date is None, uses the most recent snapshot date.
        Optionally filter by direction (overweight, underweight, etf_only, benchmark_only).
        """
        # Resolve the fund
        fund_result = await self._db.execute(
            select(Fund).where(Fund.ticker == fund_ticker)
        )
        fund = fund_result.scalar_one_or_none()
        if fund is None:
            logger.warning("Fund not found: %s", fund_ticker)
            return []

        # Resolve the date
        if target_date is None:
            target_date = await self._get_latest_deviation_date()
            if target_date is None:
                return []

        # Build query
        query = (
            select(Deviation)
            .where(
                Deviation.fund_id == fund.id,
                Deviation.snapshot_date == target_date,
            )
        )

        if direction is not None:
            query = query.where(Deviation.direction == direction)

        query = query.order_by(Deviation.abs_deviation_pct.desc()).limit(limit)

        result = await self._db.execute(query)
        deviations = result.scalars().all()

        return [
            {
                "ticker": d.ticker,
                "fund_ticker": fund_ticker,
                "benchmark_ticker": await self._resolve_benchmark_ticker(d.benchmark_id),
                "snapshot_date": d.snapshot_date.isoformat(),
                "etf_weight_pct": float(d.etf_weight_pct) if d.etf_weight_pct is not None else None,
                "benchmark_weight_pct": float(d.benchmark_weight_pct) if d.benchmark_weight_pct is not None else None,
                "deviation_pct": float(d.deviation_pct),
                "abs_deviation_pct": float(d.abs_deviation_pct),
                "deviation_rank": d.deviation_rank,
                "direction": d.direction,
            }
            for d in deviations
        ]

    async def get_top_deviations_across_funds(
        self,
        target_date: date | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get top deviations across all funds by absolute deviation.

        If target_date is None, uses the most recent snapshot date.
        """
        if target_date is None:
            target_date = await self._get_latest_deviation_date()
            if target_date is None:
                return []

        query = (
            select(Deviation, Fund.ticker.label("fund_ticker"))
            .join(Fund, Deviation.fund_id == Fund.id)
            .where(Deviation.snapshot_date == target_date)
            .order_by(Deviation.abs_deviation_pct.desc())
            .limit(limit)
        )

        result = await self._db.execute(query)
        rows = result.all()

        output: list[dict] = []
        for deviation, fund_ticker in rows:
            output.append({
                "ticker": deviation.ticker,
                "fund_ticker": fund_ticker,
                "benchmark_ticker": await self._resolve_benchmark_ticker(deviation.benchmark_id),
                "snapshot_date": deviation.snapshot_date.isoformat(),
                "etf_weight_pct": float(deviation.etf_weight_pct) if deviation.etf_weight_pct is not None else None,
                "benchmark_weight_pct": float(deviation.benchmark_weight_pct) if deviation.benchmark_weight_pct is not None else None,
                "deviation_pct": float(deviation.deviation_pct),
                "abs_deviation_pct": float(deviation.abs_deviation_pct),
                "deviation_rank": deviation.deviation_rank,
                "direction": deviation.direction,
            })
        return output

    async def get_stock_holders(
        self,
        stock_ticker: str,
        target_date: date | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Find which funds hold a specific stock, with their weight and deviation.

        If target_date is None, uses the most recent snapshot date.
        """
        if target_date is None:
            target_date = await self._get_latest_deviation_date()
            if target_date is None:
                return []

        query = (
            select(Deviation, Fund.ticker.label("fund_ticker"), Fund.name.label("fund_name"))
            .join(Fund, Deviation.fund_id == Fund.id)
            .where(
                Deviation.ticker == stock_ticker.upper(),
                Deviation.snapshot_date == target_date,
            )
            .order_by(Deviation.abs_deviation_pct.desc())
            .limit(limit)
        )

        result = await self._db.execute(query)
        rows = result.all()

        output: list[dict] = []
        for deviation, fund_ticker, fund_name in rows:
            output.append({
                "stock_ticker": stock_ticker.upper(),
                "fund_ticker": fund_ticker,
                "fund_name": fund_name,
                "snapshot_date": deviation.snapshot_date.isoformat(),
                "etf_weight_pct": float(deviation.etf_weight_pct) if deviation.etf_weight_pct is not None else None,
                "benchmark_weight_pct": float(deviation.benchmark_weight_pct) if deviation.benchmark_weight_pct is not None else None,
                "deviation_pct": float(deviation.deviation_pct),
                "abs_deviation_pct": float(deviation.abs_deviation_pct),
                "direction": deviation.direction,
            })
        return output

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_latest_deviation_date(self) -> date | None:
        """Get the most recent snapshot_date in the deviations table."""
        result = await self._db.execute(
            select(func.max(Deviation.snapshot_date))
        )
        latest = result.scalar_one_or_none()
        if latest is None:
            logger.warning("No deviations found in database")
        return latest

    async def _resolve_benchmark_ticker(self, benchmark_id: str) -> str | None:
        """Resolve a benchmark ID to its ticker symbol."""
        result = await self._db.execute(
            select(Benchmark.ticker).where(Benchmark.id == benchmark_id)
        )
        return result.scalar_one_or_none()
