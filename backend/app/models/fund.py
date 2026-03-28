from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin


class Fund(IDMixin, TimestampMixin, Base):
    __tablename__ = "funds"

    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="transparent"
    )
    asset_class: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="equity"
    )
    benchmark_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("benchmarks.id"), nullable=True
    )
    aum: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    expense_ratio: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    inception_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_holdings_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    data_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unknown"
    )

    benchmark = relationship("Benchmark", back_populates="funds")
    holdings_snapshots = relationship("HoldingsSnapshot", back_populates="fund")
    deviations = relationship(
        "Deviation", back_populates="fund", foreign_keys="Deviation.fund_id"
    )
