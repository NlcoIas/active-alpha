"""Service for fetching and storing benchmark (index ETF) holdings via multi-source aggregator."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.aggregator import HoldingsAggregator
from app.database import engine
from app.models import Benchmark
from app.utils.bulk_ops import bulk_upsert_benchmark_holdings
from app.utils.ticker_normalizer import TickerNormalizer

logger = logging.getLogger(__name__)


class BenchmarkService:
    """Fetches benchmark ETF holdings via aggregator, normalizes, and stores them."""

    def __init__(
        self,
        db: AsyncSession,
        aggregator: HoldingsAggregator,
        normalizer: TickerNormalizer,
    ) -> None:
        self._db = db
        self._aggregator = aggregator
        self._normalizer = normalizer

    async def fetch_and_store_benchmark_holdings(
        self,
        benchmark_id: str,
        benchmark_ticker: str,
        target_date: date,
    ) -> int:
        """Fetch holdings for a single benchmark, normalize, and store.

        Returns the count of holdings stored.
        """
        logger.info(
            "Fetching benchmark holdings for %s (id=%s) on %s",
            benchmark_ticker, benchmark_id, target_date,
        )

        raw_holdings = await self._aggregator.fetch_holdings(benchmark_ticker, target_date)

        if not raw_holdings:
            logger.warning(
                "No holdings returned for benchmark %s on %s",
                benchmark_ticker, target_date,
            )
            return 0

        fetched_at = datetime.now(timezone.utc)
        source = self._aggregator.get_provider_name(benchmark_ticker).lower()
        normalized_rows: list[dict] = []

        for holding in raw_holdings:
            raw_ticker = holding.get("ticker", "")
            normalized_ticker = self._normalizer.normalize(raw_ticker)

            # Filter non-equity positions
            if normalized_ticker is None:
                logger.debug(
                    "Filtered non-equity position: %s in benchmark %s",
                    raw_ticker, benchmark_ticker,
                )
                continue

            weight_pct = holding.get("weight_pct")
            if weight_pct is None:
                logger.debug(
                    "Skipping holding with no weight: %s in benchmark %s",
                    normalized_ticker, benchmark_ticker,
                )
                continue

            try:
                weight_val = float(weight_pct)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid weight_pct '%s' for %s in benchmark %s",
                    weight_pct, normalized_ticker, benchmark_ticker,
                )
                continue

            normalized_rows.append({
                "ticker": normalized_ticker,
                "name": holding.get("name"),
                "weight_pct": weight_val,
                "source": source,
                "fetched_at": fetched_at,
            })

        if not normalized_rows:
            logger.warning(
                "All holdings for benchmark %s were filtered out", benchmark_ticker
            )
            return 0

        # Bulk upsert via raw connection
        async with engine.connect() as conn:
            count = await bulk_upsert_benchmark_holdings(
                conn, benchmark_id, target_date, normalized_rows,
            )
            await conn.commit()

        # Update benchmark metadata
        result = await self._db.execute(
            select(Benchmark).where(Benchmark.id == benchmark_id)
        )
        benchmark = result.scalar_one_or_none()
        if benchmark is not None:
            benchmark.last_holdings_date = target_date
            benchmark.constituent_count = len(normalized_rows)
            await self._db.commit()

        logger.info(
            "Stored %d holdings for benchmark %s on %s",
            count, benchmark_ticker, target_date,
        )
        return count

    async def fetch_all_benchmarks(
        self,
        target_date: date,
    ) -> dict[str, int]:
        """Fetch holdings for all active benchmarks in the database.

        Returns a dict mapping benchmark ticker to the count of holdings stored.
        """
        result = await self._db.execute(
            select(Benchmark).where(Benchmark.is_active.is_(True))
        )
        benchmarks = result.scalars().all()

        if not benchmarks:
            logger.warning("No active benchmarks found in database")
            return {}

        counts: dict[str, int] = {}

        for benchmark in benchmarks:
            try:
                count = await self.fetch_and_store_benchmark_holdings(
                    benchmark.id, benchmark.ticker, target_date,
                )
                counts[benchmark.ticker] = count
            except Exception:
                logger.exception(
                    "Failed to fetch benchmark %s, skipping", benchmark.ticker
                )
                counts[benchmark.ticker] = 0

        logger.info(
            "Fetched all benchmarks: %s",
            {k: v for k, v in counts.items()},
        )
        return counts
