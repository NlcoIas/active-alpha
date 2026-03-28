from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def generate_cuid() -> str:
    """Generate a cuid-like ID using uuid4 hex."""
    import uuid

    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


class IDMixin:
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=generate_cuid,
    )
