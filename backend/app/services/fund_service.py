"""Service for querying fund data."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fund

logger = logging.getLogger(__name__)


class FundService:
    """Read-only queries against the funds table."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_funds(
        self,
        is_active: bool | None = True,
        benchmark_ticker: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Fund], int, str | None]:
        """List funds with optional filters and cursor pagination.

        Args:
            is_active: Filter by active status. None returns all.
            benchmark_ticker: Filter to funds linked to this benchmark ticker.
            limit: Maximum results to return.
            cursor: Cursor (fund ID) for keyset pagination; returns funds after this ID.

        Returns:
            Tuple of (funds_list, total_count, next_cursor).
            next_cursor is None if there are no more results.
        """
        # Base query
        query = select(Fund)
        count_query = select(func.count(Fund.id))

        # Apply filters
        if is_active is not None:
            query = query.where(Fund.is_active.is_(is_active))
            count_query = count_query.where(Fund.is_active.is_(is_active))

        if benchmark_ticker is not None:
            from app.models import Benchmark

            # Subquery to resolve benchmark ID from ticker
            benchmark_subq = (
                select(Benchmark.id)
                .where(Benchmark.ticker == benchmark_ticker)
                .scalar_subquery()
            )
            query = query.where(Fund.benchmark_id == benchmark_subq)
            count_query = count_query.where(Fund.benchmark_id == benchmark_subq)

        # Cursor pagination (keyset on id, alphabetical by ticker for stable order)
        query = query.order_by(Fund.ticker.asc(), Fund.id.asc())

        if cursor is not None:
            # Get the ticker for the cursor fund to enable keyset pagination
            cursor_result = await self._db.execute(
                select(Fund.ticker).where(Fund.id == cursor)
            )
            cursor_ticker = cursor_result.scalar_one_or_none()

            if cursor_ticker is not None:
                # Keyset: after (cursor_ticker, cursor_id)
                query = query.where(
                    (Fund.ticker > cursor_ticker)
                    | ((Fund.ticker == cursor_ticker) & (Fund.id > cursor))
                )

        # Fetch one extra to determine if there are more results
        query = query.limit(limit + 1)

        # Execute both queries
        result = await self._db.execute(query)
        funds = list(result.scalars().all())

        count_result = await self._db.execute(count_query)
        total_count = count_result.scalar_one()

        # Determine next cursor
        next_cursor: str | None = None
        if len(funds) > limit:
            funds = funds[:limit]
            next_cursor = funds[-1].id

        return funds, total_count, next_cursor

    async def get_fund(self, ticker: str) -> Fund | None:
        """Get a single fund by ticker symbol."""
        result = await self._db.execute(
            select(Fund).where(Fund.ticker == ticker.upper())
        )
        return result.scalar_one_or_none()

    async def get_fund_count(self) -> int:
        """Get total count of funds in the database."""
        result = await self._db.execute(select(func.count(Fund.id)))
        return result.scalar_one()
