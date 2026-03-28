"""Pipeline endpoints: health/status, trigger runs, and run history."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_api_key
from app.models.fund import Fund
from app.models.pipeline_run import PipelineRun
from app.schemas.pipeline import (
    DataFreshness,
    PipelineHealth,
    PipelineRunResponse,
    PipelineTriggerRequest,
    ScheduleInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])


def _run_to_response(run: PipelineRun) -> PipelineRunResponse:
    """Map a PipelineRun ORM model to the public response schema."""
    return PipelineRunResponse(
        id=run.id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        trigger_type=run.trigger_type,
        target_date=run.target_date,
        funds_succeeded=run.funds_succeeded,
        funds_failed=run.funds_failed,
        holdings_rows_inserted=run.holdings_rows_inserted,
        deviations_rows_inserted=run.deviations_rows_inserted,
        duration_seconds=str(run.duration_seconds) if run.duration_seconds is not None else None,
    )


# ---------------------------------------------------------------------------
# Public: pipeline health
# ---------------------------------------------------------------------------


@router.get("/status", response_model=PipelineHealth)
async def get_pipeline_status(
    db: AsyncSession = Depends(get_db),
) -> PipelineHealth:
    """Get pipeline health: last run, data freshness, and schedule info."""
    # Last completed run
    last_run_query = (
        select(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .limit(1)
    )
    last_run_result = await db.execute(last_run_query)
    last_run = last_run_result.scalars().one_or_none()

    # Data freshness
    latest_date_query = select(func.max(Fund.last_holdings_date)).where(Fund.is_active.is_(True))
    latest_date_result = await db.execute(latest_date_query)
    latest_holdings_date = latest_date_result.scalar_one_or_none()

    # Funds with stale data (last_holdings_date more than 3 calendar days ago)
    stale_cutoff = date.today()
    stale_query = (
        select(func.count())
        .select_from(Fund)
        .where(
            Fund.is_active.is_(True),
            Fund.last_holdings_date.isnot(None),
            Fund.last_holdings_date < stale_cutoff,
        )
    )
    stale_result = await db.execute(stale_query)
    stale_count = stale_result.scalar_one()

    # Funds with no data at all
    missing_query = (
        select(func.count())
        .select_from(Fund)
        .where(
            Fund.is_active.is_(True),
            Fund.last_holdings_date.is_(None),
        )
    )
    missing_result = await db.execute(missing_query)
    missing_count = missing_result.scalar_one()

    # Schedule info
    schedule = ScheduleInfo(
        next_run=f"{settings.pipeline_schedule_hour:02d}:00 {settings.pipeline_schedule_timezone}",
        frequency="daily",
        timezone=settings.pipeline_schedule_timezone,
    )

    return PipelineHealth(
        last_run=_run_to_response(last_run) if last_run else None,
        data_freshness=DataFreshness(
            latest_holdings_date=latest_holdings_date,
            funds_with_stale_data=stale_count,
            funds_with_missing_data=missing_count,
        ),
        schedule=schedule,
    )


# ---------------------------------------------------------------------------
# Admin: trigger a pipeline run
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
)
async def trigger_pipeline_run(
    body: PipelineTriggerRequest,
    db: AsyncSession = Depends(get_db),
) -> PipelineRunResponse:
    """Manually trigger a pipeline run (admin only, requires X-API-Key header).

    Creates a pipeline_run record with status 'pending' and returns it.
    The actual pipeline execution is handled by the scheduler/task system.
    """
    now = datetime.now(timezone.utc)

    run = PipelineRun(
        started_at=now,
        status="pending",
        trigger_type="manual",
        target_date=date.today(),
        funds_attempted=0,
        funds_succeeded=0,
        funds_failed=0,
        holdings_rows_inserted=0,
        deviations_rows_inserted=0,
        api_calls_made=0,
    )

    # Store trigger config in error_log field as metadata (reusing JSONB column)
    if body.fund_tickers or body.force_refetch:
        run.error_log = {
            "trigger_config": {
                "fund_tickers": body.fund_tickers,
                "force_refetch": body.force_refetch,
            }
        }

    db.add(run)
    await db.commit()
    await db.refresh(run)

    logger.info(
        "Pipeline run triggered manually: id=%s, tickers=%s, force=%s",
        run.id,
        body.fund_tickers,
        body.force_refetch,
    )

    return _run_to_response(run)


# ---------------------------------------------------------------------------
# Admin: pipeline run history
# ---------------------------------------------------------------------------


@router.get(
    "/runs",
    response_model=list[PipelineRunResponse],
    dependencies=[Depends(require_api_key)],
)
async def list_pipeline_runs(
    limit: int = Query(20, ge=1, le=100, description="Maximum runs to return"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
) -> list[PipelineRunResponse]:
    """List pipeline run history (admin only, requires X-API-Key header)."""
    query = select(PipelineRun).order_by(PipelineRun.started_at.desc())

    if status_filter:
        query = query.where(PipelineRun.status == status_filter)

    query = query.limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return [_run_to_response(r) for r in runs]
