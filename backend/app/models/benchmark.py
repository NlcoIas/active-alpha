from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin


class Benchmark(IDMixin, Base):
    __tablename__ = "benchmarks"

    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    index_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    constituent_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_holdings_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    funds = relationship("Fund", back_populates="benchmark")
    holdings = relationship("BenchmarkHolding", back_populates="benchmark")
