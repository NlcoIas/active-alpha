from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin


class TickerMapping(IDMixin, Base):
    __tablename__ = "ticker_mappings"

    old_ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    new_ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
