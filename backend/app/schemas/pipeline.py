"""Pipeline-related Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PipelineRunResponse(BaseModel):
    """Public representation of a pipeline run."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    trigger_type: str
    target_date: date
    funds_succeeded: int
    funds_failed: int
    holdings_rows_inserted: int
    deviations_rows_inserted: int
    duration_seconds: str | None = None


class DataFreshness(BaseModel):
    """Snapshot of data currency across tracked funds."""

    latest_holdings_date: date | None = None
    funds_with_stale_data: int = 0
    funds_with_missing_data: int = 0


class ScheduleInfo(BaseModel):
    """Information about the pipeline schedule."""

    next_run: str | None = None
    frequency: str = "daily"
    timezone: str = "US/Eastern"


class PipelineHealth(BaseModel):
    """Composite health check for the pipeline subsystem."""

    last_run: PipelineRunResponse | None = None
    data_freshness: DataFreshness
    schedule: ScheduleInfo


class PipelineTriggerRequest(BaseModel):
    """Request body for manually triggering a pipeline run."""

    fund_tickers: list[str] | None = None
    force_refetch: bool = False
