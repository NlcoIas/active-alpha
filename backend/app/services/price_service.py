"""Service for fetching and storing daily stock price data via yfinance."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.database import engine
from app.models.base import generate_cuid

logger = logging.getLogger(__name__)


class PriceService:
    """Fetches daily OHLCV data from yfinance and bulk-upserts into stock_prices."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def fetch_and_store_prices(
        self,
        tickers: list[str],
        start_date: date,
        end_date: date | None = None,
    ) -> int:
        """Fetch daily OHLCV data for the given tickers and upsert into stock_prices.

        Args:
            tickers: List of stock tickers to fetch.
            start_date: Start date for the price range.
            end_date: End date (defaults to today).

        Returns:
            Number of price rows upserted.
        """
        if not tickers:
            return 0

        if end_date is None:
            end_date = date.today()

        logger.info(
            "Fetching prices for %d tickers from %s to %s",
            len(tickers), start_date, end_date,
        )

        # yfinance download is synchronous, so we run it directly.
        # For multiple tickers, yfinance batches efficiently.
        try:
            df = yf.download(
                tickers=tickers,
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                auto_adjust=False,
                progress=False,
                threads=True,
            )
        except Exception:
            logger.exception("Failed to download prices from yfinance")
            return 0

        if df.empty:
            logger.warning("No price data returned from yfinance")
            return 0

        rows = self._dataframe_to_rows(df, tickers)
        if not rows:
            logger.warning("No valid price rows extracted from yfinance data")
            return 0

        async with engine.connect() as conn:
            count = await self._bulk_upsert_prices(conn, rows)
            await conn.commit()

        logger.info("Upserted %d price rows for %d tickers", count, len(tickers))
        return count

    async def get_prices(
        self,
        tickers: list[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Get prices from the database for the given tickers and date range.

        Returns a DataFrame with columns: ticker, price_date, close_price, adj_close.
        """
        query = text("""
            SELECT ticker, price_date, close_price, adj_close
            FROM stock_prices
            WHERE ticker = ANY(:tickers)
              AND price_date >= :start_date
              AND price_date <= :end_date
            ORDER BY ticker, price_date
        """)

        async with engine.connect() as conn:
            result = await conn.execute(
                query,
                {
                    "tickers": tickers,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame(columns=["ticker", "price_date", "close_price", "adj_close"])

        return pd.DataFrame(rows, columns=["ticker", "price_date", "close_price", "adj_close"])

    async def ensure_prices(
        self,
        tickers: list[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Get prices from the database, fetching any missing tickers from yfinance.

        Returns a DataFrame with columns: ticker, price_date, close_price, adj_close.
        """
        df = await self.get_prices(tickers, start_date, end_date)

        # Find tickers that have no data at all
        existing_tickers = set(df["ticker"].unique()) if not df.empty else set()
        missing_tickers = [t for t in tickers if t not in existing_tickers]

        if missing_tickers:
            logger.info(
                "Missing prices for %d tickers, fetching from yfinance: %s",
                len(missing_tickers),
                missing_tickers[:10],
            )
            await self.fetch_and_store_prices(missing_tickers, start_date, end_date)
            # Re-query to include newly fetched data
            df = await self.get_prices(tickers, start_date, end_date)

        return df

    def _dataframe_to_rows(
        self, df: pd.DataFrame, tickers: list[str]
    ) -> list[dict]:
        """Convert yfinance DataFrame to a list of dicts for bulk upsert."""
        rows: list[dict] = []

        if len(tickers) == 1:
            # Single ticker: columns are simple (Open, High, Low, Close, Adj Close, Volume)
            ticker = tickers[0]
            for idx, row in df.iterrows():
                price_date = idx.date() if hasattr(idx, "date") else idx
                close_val = row.get("Close")
                if pd.isna(close_val):
                    continue
                rows.append({
                    "ticker": ticker,
                    "price_date": price_date,
                    "open_price": None if pd.isna(row.get("Open")) else float(row["Open"]),
                    "high_price": None if pd.isna(row.get("High")) else float(row["High"]),
                    "low_price": None if pd.isna(row.get("Low")) else float(row["Low"]),
                    "close_price": float(close_val),
                    "adj_close": float(row.get("Adj Close", close_val)),
                    "volume": None if pd.isna(row.get("Volume")) else int(row["Volume"]),
                })
        else:
            # Multiple tickers: MultiIndex columns like (Open, AAPL), (Close, AAPL), etc.
            for ticker in tickers:
                try:
                    ticker_data = df.xs(ticker, axis=1, level=1) if isinstance(
                        df.columns, pd.MultiIndex
                    ) else df
                except KeyError:
                    logger.warning("No data for ticker %s in yfinance response", ticker)
                    continue

                for idx, row in ticker_data.iterrows():
                    price_date = idx.date() if hasattr(idx, "date") else idx
                    close_val = row.get("Close")
                    if pd.isna(close_val):
                        continue
                    rows.append({
                        "ticker": ticker,
                        "price_date": price_date,
                        "open_price": None if pd.isna(row.get("Open")) else float(row["Open"]),
                        "high_price": None if pd.isna(row.get("High")) else float(row["High"]),
                        "low_price": None if pd.isna(row.get("Low")) else float(row["Low"]),
                        "close_price": float(close_val),
                        "adj_close": float(row.get("Adj Close", close_val)),
                        "volume": None if pd.isna(row.get("Volume")) else int(row["Volume"]),
                    })

        return rows

    @staticmethod
    async def _bulk_upsert_prices(
        conn: AsyncConnection, rows: list[dict]
    ) -> int:
        """Bulk upsert price rows into stock_prices table."""
        if not rows:
            return 0

        stmt = text("""
            INSERT INTO stock_prices
                (id, ticker, price_date, open_price, high_price, low_price,
                 close_price, adj_close, volume, source)
            VALUES
                (:id, :ticker, :price_date, :open_price, :high_price, :low_price,
                 :close_price, :adj_close, :volume, :source)
            ON CONFLICT (ticker, price_date) DO UPDATE SET
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                adj_close = EXCLUDED.adj_close,
                volume = EXCLUDED.volume
        """)

        params = [
            {
                "id": generate_cuid(),
                "ticker": row["ticker"],
                "price_date": row["price_date"],
                "open_price": row.get("open_price"),
                "high_price": row.get("high_price"),
                "low_price": row.get("low_price"),
                "close_price": row["close_price"],
                "adj_close": row.get("adj_close", row["close_price"]),
                "volume": row.get("volume"),
                "source": "yfinance",
            }
            for row in rows
        ]

        # Batch in chunks of 1000 to avoid parameter limits
        batch_size = 1000
        for i in range(0, len(params), batch_size):
            batch = params[i : i + batch_size]
            await conn.execute(stmt, batch)

        return len(params)
