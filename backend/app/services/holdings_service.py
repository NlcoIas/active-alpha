"""Service for fetching and storing ETF holdings via multi-source aggregator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.aggregator import HoldingsAggregator
from app.database import engine
from app.utils.bulk_ops import bulk_upsert_holdings
from app.utils.ticker_normalizer import TickerNormalizer
from app.utils.validation import HoldingsValidator

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    funds_processed: int = 0
    funds_failed: int = 0
    total_holdings: int = 0
    errors: dict[str, str] = field(default_factory=dict)


class HoldingsService:
    """Fetches ETF holdings via aggregator, normalizes, validates, and stores them."""

    def __init__(
        self,
        db: AsyncSession,
        aggregator: HoldingsAggregator,
        normalizer: TickerNormalizer,
    ) -> None:
        self._db = db
        self._aggregator = aggregator
        self._normalizer = normalizer
        self._validator = HoldingsValidator()

    async def fetch_and_store_holdings(
        self,
        fund_id: str,
        fund_ticker: str,
        target_date: date,
    ) -> int:
        """Fetch holdings for a single fund, normalize, validate, and store.

        Returns the count of holdings stored.
        """
        logger.info(
            "Fetching holdings for %s (fund_id=%s) on %s",
            fund_ticker, fund_id, target_date,
        )

        # Fetch raw holdings from the best available provider
        raw_holdings = await self._aggregator.fetch_holdings(fund_ticker, target_date)

        if not raw_holdings:
            logger.warning("No holdings returned for %s on %s", fund_ticker, target_date)
            return 0

        # Normalize tickers and filter non-equity positions
        fetched_at = datetime.now(timezone.utc)
        source = self._aggregator.get_provider_name(fund_ticker).lower()
        normalized_rows: list[dict] = []

        for holding in raw_holdings:
            raw_ticker = holding.get("ticker", "")
            normalized_ticker = self._normalizer.normalize(raw_ticker)

            # Filter non-equity positions (cash, derivatives, etc.)
            if normalized_ticker is None:
                logger.debug(
                    "Filtered non-equity position: %s in %s", raw_ticker, fund_ticker
                )
                continue

            weight_pct = holding.get("weight_pct")
            if weight_pct is None:
                logger.debug(
                    "Skipping holding with no weight: %s in %s",
                    normalized_ticker, fund_ticker,
                )
                continue

            try:
                weight_val = float(weight_pct)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid weight_pct '%s' for %s in %s",
                    weight_pct, normalized_ticker, fund_ticker,
                )
                continue

            normalized_rows.append({
                "ticker": normalized_ticker,
                "name": holding.get("name"),
                "asset_type": "equity",
                "weight_pct": weight_val,
                "shares": _safe_float(holding.get("shares")),
                "market_value": _safe_float(holding.get("market_value")),
                "is_stale": False,
                "source": source,
                "fetched_at": fetched_at,
            })

        if not normalized_rows:
            logger.warning(
                "All holdings for %s were filtered out (non-equity or missing weight)",
                fund_ticker,
            )
            return 0

        # Validate the snapshot
        validation = self._validator.validate_snapshot(
            fund_ticker, target_date, normalized_rows, expected_date=target_date,
        )

        if validation.errors:
            logger.warning(
                "Validation errors for %s: %s", fund_ticker, validation.errors
            )

        if validation.warnings:
            logger.info(
                "Validation warnings for %s: %s", fund_ticker, validation.warnings
            )

        # Mark as stale if validator detects staleness
        if validation.is_stale:
            for row in normalized_rows:
                row["is_stale"] = True
            logger.info("Marking holdings for %s as stale", fund_ticker)

        # Bulk upsert via raw connection (bulk_ops requires AsyncConnection, not session)
        async with engine.connect() as conn:
            count = await bulk_upsert_holdings(
                conn, fund_id, target_date, normalized_rows,
            )
            await conn.commit()

        logger.info(
            "Stored %d holdings for %s on %s (weight_sum=%.2f%%, stale=%s)",
            count, fund_ticker, target_date, validation.weight_sum, validation.is_stale,
        )
        return count

    async def fetch_and_store_batch(
        self,
        funds: list[tuple[str, str]],
        target_date: date,
        batch_size: int = 10,
    ) -> BatchResult:
        """Process multiple funds in batches with concurrency control.

        Args:
            funds: List of (fund_id, fund_ticker) tuples.
            target_date: Date to fetch holdings for.
            batch_size: Maximum concurrent fund fetches.

        Returns:
            BatchResult with processing summary.
        """
        result = BatchResult()
        semaphore = asyncio.Semaphore(batch_size)

        async def process_one(fund_id: str, fund_ticker: str) -> None:
            async with semaphore:
                try:
                    count = await self.fetch_and_store_holdings(
                        fund_id, fund_ticker, target_date,
                    )
                    result.funds_processed += 1
                    result.total_holdings += count
                except Exception as exc:
                    result.funds_failed += 1
                    result.errors[fund_ticker] = f"Provider error: {exc}"
                    logger.exception(
                        "Failed to fetch holdings for %s: %s", fund_ticker, exc
                    )

        # Launch all tasks with semaphore-controlled concurrency
        tasks = [
            asyncio.create_task(process_one(fund_id, fund_ticker))
            for fund_id, fund_ticker in funds
        ]
        await asyncio.gather(*tasks)

        logger.info(
            "Batch complete: %d processed, %d failed, %d total holdings",
            result.funds_processed, result.funds_failed, result.total_holdings,
        )
        return result


def _safe_float(value: object) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
