from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin


class BenchmarkHolding(IDMixin, Base):
    __tablename__ = "benchmark_holdings"

    benchmark_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("benchmarks.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight_pct: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="fmp"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    benchmark = relationship("Benchmark", back_populates="holdings")

    __table_args__ = (
        UniqueConstraint(
            "benchmark_id", "snapshot_date", "ticker",
            name="uq_benchmark_bench_date_ticker",
        ),
        Index("ix_benchmark_bench_date", "benchmark_id", snapshot_date.desc()),
    )
