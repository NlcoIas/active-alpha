"""Common schemas used across the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response shape for all API errors."""

    error: str
    code: str
    details: Any = None


class CursorPagination(BaseModel):
    """Cursor-based pagination metadata."""

    next_cursor: str | None = None
    has_more: bool = False
    total_count: int = 0
