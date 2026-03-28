"""ARK Invest ETF holdings client.

Fetches daily holdings CSVs published by ARK for their 6 ETFs.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ARK_URLS: dict[str, str] = {
    "ARKK": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv",
    "ARKW": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv",
    "ARKG": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv",
    "ARKF": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv",
    "ARKQ": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_AUTONOMOUS_TECH._&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv",
    "ARKX": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.csv",
}

# Flexible column name mapping — ARK CSVs have inconsistent casing/spacing
_COLUMN_ALIASES: dict[str, list[str]] = {
    "ticker": ["ticker", "symbol"],
    "name": ["company", "name", "security name"],
    "weight_pct": ["weight (%)", "weight(%)", "weight", "percentage"],
    "shares": ["shares", "shares held"],
    "market_value": ["market value ($)", "market value($)", "market value", "marketvalue"],
}


def _find_column(headers: list[str], aliases: list[str]) -> str | None:
    """Find the actual column name from a list of possible aliases."""
    lower_headers = {h.lower().strip(): h for h in headers}
    for alias in aliases:
        if alias.lower() in lower_headers:
            return lower_headers[alias.lower()]
    return None


def _safe_float(value: str | None) -> float | None:
    """Parse a string to float, stripping commas and dollar signs."""
    if value is None:
        return None
    cleaned = value.strip().replace(",", "").replace("$", "").replace("%", "")
    if not cleaned or cleaned == "-" or cleaned.lower() == "n/a":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


class ARKClient:
    """Client for fetching ARK Invest ETF holdings from their public CSVs."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "ActiveAlpha/1.0 (ETF research tool)"},
        )

    def supports(self, ticker: str) -> bool:
        """Check if this provider can fetch holdings for this ticker."""
        return ticker.upper() in ARK_URLS

    async def fetch_holdings(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch holdings for an ARK ETF.

        Returns list of dicts with keys: ticker, name, weight_pct, shares, market_value.
        Weight_pct is in percentage points (e.g. 7.24 means 7.24%).
        Returns empty list on any error.
        """
        ticker_upper = ticker.upper()
        url = ARK_URLS.get(ticker_upper)
        if url is None:
            logger.warning("ARK: unsupported ticker %s", ticker)
            return []

        try:
            response = await self._http.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "ARK: HTTP %d fetching %s holdings: %s",
                exc.response.status_code,
                ticker_upper,
                exc,
            )
            return []
        except httpx.HTTPError as exc:
            logger.error("ARK: network error fetching %s holdings: %s", ticker_upper, exc)
            return []

        try:
            return self._parse_csv(response.text, ticker_upper)
        except Exception:
            logger.exception("ARK: failed to parse CSV for %s", ticker_upper)
            return []

    def _parse_csv(self, text: str, ticker: str) -> list[dict[str, Any]]:
        """Parse ARK CSV text into normalized holdings list."""
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            logger.warning("ARK: empty CSV for %s", ticker)
            return []

        headers = list(reader.fieldnames)

        col_ticker = _find_column(headers, _COLUMN_ALIASES["ticker"])
        col_name = _find_column(headers, _COLUMN_ALIASES["name"])
        col_weight = _find_column(headers, _COLUMN_ALIASES["weight_pct"])
        col_shares = _find_column(headers, _COLUMN_ALIASES["shares"])
        col_market_value = _find_column(headers, _COLUMN_ALIASES["market_value"])

        if col_ticker is None and col_name is None:
            logger.warning(
                "ARK: could not identify ticker or name columns in CSV for %s. Headers: %s",
                ticker,
                headers,
            )
            return []

        holdings: list[dict[str, Any]] = []

        for row in reader:
            holding_ticker = (row.get(col_ticker) or "").strip() if col_ticker else ""
            holding_name = (row.get(col_name) or "").strip() if col_name else ""

            # Skip empty rows or cash positions without a ticker
            if not holding_ticker and not holding_name:
                continue

            weight = _safe_float(row.get(col_weight)) if col_weight else None
            shares = _safe_float(row.get(col_shares)) if col_shares else None
            market_value = _safe_float(row.get(col_market_value)) if col_market_value else None

            holdings.append(
                {
                    "ticker": holding_ticker,
                    "name": holding_name,
                    "weight_pct": weight,
                    "shares": shares,
                    "market_value": market_value,
                }
            )

        logger.info("ARK: parsed %d holdings for %s", len(holdings), ticker)
        return holdings

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> ARKClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
