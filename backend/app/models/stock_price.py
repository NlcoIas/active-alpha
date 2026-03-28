from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin


class StockPrice(IDMixin, Base):
    __tablename__ = "stock_prices"

    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    adj_close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="fmp"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("ticker", "price_date", name="uq_prices_ticker_date"),
        Index("ix_prices_ticker_date", "ticker", price_date.desc()),
    )
