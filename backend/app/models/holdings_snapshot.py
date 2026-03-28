from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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


class HoldingsSnapshot(IDMixin, Base):
    __tablename__ = "holdings_snapshots"

    fund_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("funds.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="equity"
    )
    weight_pct: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
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

    fund = relationship("Fund", back_populates="holdings_snapshots")

    __table_args__ = (
        UniqueConstraint("fund_id", "snapshot_date", "ticker", name="uq_holdings_fund_date_ticker"),
        Index("ix_holdings_fund_date", "fund_id", snapshot_date.desc()),
        Index("ix_holdings_date", snapshot_date.desc()),
    )
