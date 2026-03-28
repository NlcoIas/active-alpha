from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin


class Deviation(IDMixin, Base):
    __tablename__ = "deviations"

    fund_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("funds.id"), nullable=False
    )
    benchmark_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("benchmarks.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    etf_weight_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 5), nullable=True
    )
    benchmark_weight_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 5), nullable=True
    )
    deviation_pct: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    abs_deviation_pct: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    deviation_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    fund = relationship("Fund", back_populates="deviations", foreign_keys=[fund_id])
    benchmark = relationship("Benchmark")

    __table_args__ = (
        UniqueConstraint(
            "fund_id", "benchmark_id", "snapshot_date", "ticker",
            name="uq_deviations_fund_bench_date_ticker",
        ),
        Index("ix_deviations_fund_date", "fund_id", snapshot_date.desc()),
        Index("ix_deviations_ticker_date", "ticker", snapshot_date.desc()),
        Index("ix_deviations_abs", "fund_id", "snapshot_date", abs_deviation_pct.desc()),
    )
