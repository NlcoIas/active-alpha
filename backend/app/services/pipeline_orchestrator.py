"""Pipeline orchestrator: runs the daily ETF holdings pipeline end-to-end."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from time import monotonic

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.aggregator import HoldingsAggregator
from app.models import Fund, PipelineRun
from app.services.benchmark_service import BenchmarkService
from app.services.deviation_service import DeviationService
from app.services.holdings_service import HoldingsService
from app.utils.market_calendar import is_trading_day, previous_trading_day
from app.utils.ticker_normalizer import TickerNormalizer

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when the pipeline cannot proceed."""


class PipelineOrchestrator:
    """Orchestrates the daily data pipeline: holdings -> benchmarks -> deviations."""

    def __init__(
        self,
        db_factory: async_sessionmaker[AsyncSession],
        aggregator: HoldingsAggregator,
    ) -> None:
        self._db_factory = db_factory
        self._aggregator = aggregator

    async def run_daily_pipeline(
        self,
        target_date: date | None = None,
        trigger_type: str = "scheduled",
    ) -> PipelineRun:
        """Run the full daily pipeline.

        Stages:
        1. Fetch and store holdings for all active funds.
        2. Fetch and store benchmark holdings.
        3. Calculate deviations for all fund-benchmark pairs.

        Args:
            target_date: The trading date to fetch data for.
                         Defaults to most recent trading day.
            trigger_type: How the pipeline was triggered (scheduled, manual, backfill).

        Returns:
            PipelineRun record with results.
        """
        start_time = monotonic()
        now = datetime.now(timezone.utc)

        # Resolve target date
        if target_date is None:
            target_date = previous_trading_day(date.today())

        async with self._db_factory() as db:
            # Check if target date is a trading day
            if not is_trading_day(target_date):
                logger.info(
                    "Target date %s is not a trading day, skipping pipeline",
                    target_date,
                )
                pipeline_run = PipelineRun(
                    started_at=now,
                    completed_at=datetime.now(timezone.utc),
                    status="skipped",
                    trigger_type=trigger_type,
                    target_date=target_date,
                    duration_seconds=Decimal(str(round(monotonic() - start_time, 2))),
                )
                db.add(pipeline_run)
                await db.commit()
                await db.refresh(pipeline_run)
                return pipeline_run

            # Check if already running
            running_result = await db.execute(
                select(PipelineRun).where(PipelineRun.status == "running")
            )
            if running_result.scalar_one_or_none() is not None:
                raise PipelineError(
                    "A pipeline run is already in progress. "
                    "Wait for it to complete or mark it as failed."
                )

            # Create pipeline run record
            pipeline_run = PipelineRun(
                started_at=now,
                status="running",
                trigger_type=trigger_type,
                target_date=target_date,
            )
            db.add(pipeline_run)
            await db.commit()
            await db.refresh(pipeline_run)

        error_log: list[dict] = []
        skipped_tickers: list[str] = []
        holdings_total = 0
        deviations_total = 0
        funds_attempted = 0
        funds_succeeded = 0
        funds_failed = 0
        benchmark_failed = False

        normalizer = TickerNormalizer()

        try:
            # ----------------------------------------------------------
            # Stage 1: Fetch and store holdings for all active funds
            # ----------------------------------------------------------
            logger.info("Pipeline stage 1: Fetching fund holdings for %s", target_date)

            async with self._db_factory() as db:
                result = await db.execute(
                    select(Fund.id, Fund.ticker).where(Fund.is_active.is_(True))
                )
                fund_rows = result.all()

            funds_list = [(row.id, row.ticker) for row in fund_rows]
            funds_attempted = len(funds_list)

            if not funds_list:
                logger.warning("No active funds found, nothing to process")
            else:
                async with self._db_factory() as db:
                    holdings_svc = HoldingsService(db, self._aggregator, normalizer)
                    batch_result = await holdings_svc.fetch_and_store_batch(
                        funds_list, target_date,
                    )

                holdings_total = batch_result.total_holdings
                funds_succeeded = batch_result.funds_processed
                funds_failed = batch_result.funds_failed

                for ticker, err_msg in batch_result.errors.items():
                    error_log.append({
                        "stage": "holdings",
                        "ticker": ticker,
                        "error": err_msg,
                    })
                    skipped_tickers.append(ticker)

            # ----------------------------------------------------------
            # Stage 2: Fetch all benchmark holdings
            # ----------------------------------------------------------
            logger.info("Pipeline stage 2: Fetching benchmark holdings for %s", target_date)

            try:
                async with self._db_factory() as db:
                    benchmark_svc = BenchmarkService(db, self._aggregator, normalizer)
                    benchmark_counts = await benchmark_svc.fetch_all_benchmarks(target_date)

                logger.info("Benchmark results: %s", benchmark_counts)
                # Check if any benchmark actually got data
                benchmarks_with_data = sum(1 for c in benchmark_counts.values() if c > 0)
                if benchmarks_with_data == 0:
                    benchmark_failed = True
                    error_log.append({
                        "stage": "benchmarks",
                        "error": "No benchmark returned holdings data",
                    })
                else:
                    logger.info("%d/%d benchmarks got data", benchmarks_with_data, len(benchmark_counts))
                    for ticker, count in benchmark_counts.items():
                        if count == 0:
                            error_log.append({
                                "stage": "benchmarks",
                                "ticker": ticker,
                                "error": f"No data for benchmark {ticker}",
                            })
            except Exception as exc:
                benchmark_failed = True
                logger.error("Benchmark fetch failed: %s", exc)
                error_log.append({
                    "stage": "benchmarks",
                    "error": str(exc),
                })

            # ----------------------------------------------------------
            # Stage 3: Calculate all deviations
            # ----------------------------------------------------------
            if benchmark_failed:
                logger.warning(
                    "Skipping deviation calculation because benchmark fetch failed"
                )
                error_log.append({
                    "stage": "deviations",
                    "error": "Skipped due to benchmark failure",
                })
            else:
                logger.info("Pipeline stage 3: Calculating deviations for %s", target_date)
                try:
                    async with self._db_factory() as db:
                        deviation_svc = DeviationService(db)
                        deviations_total = await deviation_svc.calculate_all_deviations(
                            target_date,
                        )
                except Exception as exc:
                    logger.error("Deviation calculation failed: %s", exc)
                    error_log.append({
                        "stage": "deviations",
                        "error": str(exc),
                    })

            # ----------------------------------------------------------
            # Update fund metadata
            # ----------------------------------------------------------
            async with self._db_factory() as db:
                await self._update_fund_metadata(db, target_date)

            # Determine final status
            if funds_failed == 0 and not benchmark_failed and deviations_total > 0:
                status = "completed"
            elif funds_succeeded > 0:
                status = "partial_failure"
            else:
                status = "failed"

        except Exception as exc:
            logger.exception("Pipeline failed with unexpected error")
            status = "failed"
            error_log.append({
                "stage": "pipeline",
                "error": str(exc),
            })

        # ----------------------------------------------------------
        # Finalize pipeline run record
        # ----------------------------------------------------------
        duration = Decimal(str(round(monotonic() - start_time, 2)))

        async with self._db_factory() as db:
            result = await db.execute(
                select(PipelineRun).where(PipelineRun.id == pipeline_run.id)
            )
            run = result.scalar_one()
            run.completed_at = datetime.now(timezone.utc)
            run.status = status
            run.funds_attempted = funds_attempted
            run.funds_succeeded = funds_succeeded
            run.funds_failed = funds_failed
            run.holdings_rows_inserted = holdings_total
            run.deviations_rows_inserted = deviations_total
            run.api_calls_made = self._aggregator.api_calls_made
            run.duration_seconds = duration
            run.error_log = error_log if error_log else None
            run.skipped_tickers = skipped_tickers if skipped_tickers else None
            await db.commit()
            await db.refresh(run)

        logger.info(
            "Pipeline %s: status=%s, funds=%d/%d, holdings=%d, deviations=%d, "
            "duration=%.2fs, api_calls=%d",
            run.id, status, funds_succeeded, funds_attempted,
            holdings_total, deviations_total, float(duration),
            self._aggregator.api_calls_made,
        )
        return run

    async def get_status(self) -> dict:
        """Get the latest pipeline run status and data freshness info."""
        async with self._db_factory() as db:
            # Latest pipeline run
            result = await db.execute(
                select(PipelineRun)
                .order_by(PipelineRun.started_at.desc())
                .limit(1)
            )
            latest_run = result.scalar_one_or_none()

            # Data freshness: latest holdings date across all funds
            freshness_result = await db.execute(
                select(
                    func.max(Fund.last_holdings_date).label("latest_holdings_date"),
                    func.count(Fund.id).label("total_funds"),
                    func.count(Fund.last_holdings_date).label("funds_with_data"),
                ).where(Fund.is_active.is_(True))
            )
            freshness = freshness_result.one()

        return {
            "latest_run": {
                "id": latest_run.id,
                "status": latest_run.status,
                "target_date": latest_run.target_date.isoformat(),
                "started_at": latest_run.started_at.isoformat(),
                "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
                "funds_succeeded": latest_run.funds_succeeded,
                "funds_failed": latest_run.funds_failed,
                "holdings_rows_inserted": latest_run.holdings_rows_inserted,
                "deviations_rows_inserted": latest_run.deviations_rows_inserted,
                "duration_seconds": float(latest_run.duration_seconds) if latest_run.duration_seconds else None,
            } if latest_run else None,
            "data_freshness": {
                "latest_holdings_date": freshness.latest_holdings_date.isoformat() if freshness.latest_holdings_date else None,
                "total_active_funds": freshness.total_funds,
                "funds_with_data": freshness.funds_with_data,
            },
        }

    async def get_run_history(self, limit: int = 20) -> list[PipelineRun]:
        """Get recent pipeline run history."""
        async with self._db_factory() as db:
            result = await db.execute(
                select(PipelineRun)
                .order_by(PipelineRun.started_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _update_fund_metadata(
        self, db: AsyncSession, target_date: date
    ) -> None:
        """Update last_holdings_date and data_quality for funds that got new data."""
        result = await db.execute(
            select(Fund).where(Fund.is_active.is_(True))
        )
        funds = result.scalars().all()

        for fund in funds:
            if fund.last_holdings_date is None or fund.last_holdings_date < target_date:
                # Check if we actually have holdings for this date
                from sqlalchemy import exists

                from app.models import HoldingsSnapshot

                has_holdings = await db.execute(
                    select(
                        exists().where(
                            HoldingsSnapshot.fund_id == fund.id,
                            HoldingsSnapshot.snapshot_date == target_date,
                        )
                    )
                )
                if has_holdings.scalar():
                    fund.last_holdings_date = target_date
                    fund.data_quality = "good"
                elif fund.last_holdings_date is not None:
                    # Has historical data but not for this date
                    days_stale = (target_date - fund.last_holdings_date).days
                    if days_stale > 5:
                        fund.data_quality = "stale"
                    else:
                        fund.data_quality = "delayed"
                else:
                    fund.data_quality = "missing"

        await db.commit()
