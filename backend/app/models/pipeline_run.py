from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin


class PipelineRun(IDMixin, Base):
    __tablename__ = "pipeline_runs"

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="running"
    )
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    funds_attempted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    funds_succeeded: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    funds_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    holdings_rows_inserted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    deviations_rows_inserted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    api_calls_made: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    duration_seconds: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    error_log: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    skipped_tickers: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_pipeline_runs_status", "status", started_at.desc()),
    )
