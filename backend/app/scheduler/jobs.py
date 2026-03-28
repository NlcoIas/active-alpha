"""APScheduler job definitions and lifecycle management.

Uses APScheduler 3.x AsyncIOScheduler with a CronTrigger for the daily
pipeline run. The scheduler is started/stopped via the FastAPI lifespan.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_daily_pipeline() -> None:
    """Execute the daily holdings ingestion + deviation calculation pipeline.

    This is the job that APScheduler invokes on the configured cron schedule.
    It imports the pipeline orchestrator at call time to avoid circular imports
    and to ensure all app-level singletons (DB engine, aggregator) are ready.
    """
    logger.info("Scheduled daily pipeline run starting")
    try:
        # Import at runtime to avoid circular deps and ensure app is initialized
        from app.database import SessionLocal
        from app.dependencies import get_aggregator
        from app.services.pipeline_orchestrator import PipelineOrchestrator

        aggregator = get_aggregator()

        logger.info(
            "Daily pipeline triggered. Aggregator ready=%s.",
            aggregator is not None,
        )

        orchestrator = PipelineOrchestrator(SessionLocal, aggregator)
        await orchestrator.run_daily_pipeline(trigger_type="scheduled")

    except Exception:
        logger.exception("Daily pipeline run failed with unhandled exception")


def start_scheduler(app: FastAPI) -> None:
    """Create and start the APScheduler instance.

    Adds a daily cron job for the pipeline run. The scheduler is stored on
    the app's state so it can be referenced (e.g. for the /pipeline/status
    endpoint to report next_run_time).
    """
    global _scheduler  # noqa: PLW0603

    _scheduler = AsyncIOScheduler(
        job_defaults={
            "misfire_grace_time": 3600,  # Allow up to 1 hour late start
            "coalesce": True,  # If multiple misfires, run once
            "max_instances": 1,  # Never run overlapping instances
        },
    )

    _scheduler.add_job(
        _run_daily_pipeline,
        trigger=CronTrigger(
            hour=settings.pipeline_schedule_hour,
            minute=0,
            timezone=settings.pipeline_schedule_timezone,
        ),
        id="daily_pipeline",
        name="Daily Holdings Ingestion Pipeline",
        replace_existing=True,
    )

    _scheduler.start()
    app.state.scheduler = _scheduler

    next_run = _scheduler.get_job("daily_pipeline")
    logger.info(
        "Scheduler started. Daily pipeline scheduled at %02d:00 %s. Next run: %s",
        settings.pipeline_schedule_hour,
        settings.pipeline_schedule_timezone,
        next_run.next_run_time if next_run else "unknown",
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler, waiting for running jobs to finish."""
    global _scheduler  # noqa: PLW0603

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down gracefully")
        _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    """Return the current scheduler instance (if running)."""
    return _scheduler
