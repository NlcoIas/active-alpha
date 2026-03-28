"""Invesco ETF holdings client.

Fetches daily holdings CSVs from Invesco's public download endpoint.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

INVESCO_URL_TEMPLATE = (
    "https://www.invesco.com/us/financial-products/etfs/holdings/main/holdings/0"
    "?audienceType=Investor&action=download&ticker={ticker}"
)

# Known Invesco ETF tickers — can be expanded as needed
INVESCO_TICKERS: set[str] = {
    # Nasdaq / S&P
    "QQQ", "QQQM", "RSP", "SPLG",
    # Factor / Smart beta
    "SPHB", "SPHQ", "SPHD", "PRFZ",
    # Equal weight sector
    "RSPT", "RSPF", "RSPE",
    # Other popular
    "PGX", "BKLN", "PHB", "VCSH",
    "DBA", "DBB", "DBC", "DBO",
    "PDBC", "KBWB", "KBWP",
}

# Column name aliases for flexible header matching
_COLUMN_ALIASES: dict[str, list[str]] = {
    "ticker": ["holding ticker", "ticker", "symbol", "security ticker"],
    "name": ["security name", "name", "description", "holding name", "security description"],
    "weight_pct": ["weight", "weight (%)", "% of fund", "portfolio weight", "percentage"],
    "shares": ["shares/par amount", "shares", "quantity", "shares held", "par amount"],
    "market_value": ["marketvalue", "market value", "value", "market value ($)", "emv"],
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
    if not cleaned or cleaned == "-" or cleaned.lower() in ("n/a", "na", "--"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_weight(value: float | None) -> float | None:
    """Normalize weight to percentage points.

    Invesco CSVs may provide weights as either:
    - Percentage: 8.45 (meaning 8.45%)
    - Decimal: 0.0845 (meaning 8.45%)

    Heuristic: if all non-None weights are <= 1.0 and total is close to 1.0,
    treat as decimal. Otherwise treat as percentage.
    This function handles individual values; batch detection is done in _parse_csv.
    """
    return value


class InvescoClient:
    """Client for fetching Invesco ETF holdings from their public CSV endpoint."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "ActiveAlpha/1.0 (ETF research tool)"},
            follow_redirects=True,
        )

    def supports(self, ticker: str) -> bool:
        """Check if this provider can fetch holdings for this ticker."""
        return ticker.upper() in INVESCO_TICKERS

    async def fetch_holdings(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch holdings for an Invesco ETF.

        Returns list of dicts with keys: ticker, name, weight_pct, shares, market_value.
        Weight_pct is in percentage points (e.g. 7.24 means 7.24%).
        Returns empty list on any error.
        """
        ticker_upper = ticker.upper()
        url = INVESCO_URL_TEMPLATE.format(ticker=ticker_upper)

        try:
            response = await self._http.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Invesco: HTTP %d fetching %s holdings: %s",
                exc.response.status_code,
                ticker_upper,
                exc,
            )
            return []
        except httpx.HTTPError as exc:
            logger.error(
                "Invesco: network error fetching %s holdings: %s", ticker_upper, exc
            )
            return []

        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "csv" not in content_type:
            logger.warning(
                "Invesco: unexpected content-type %s for %s (may not be CSV)",
                content_type,
                ticker_upper,
            )

        try:
            return self._parse_csv(response.text, ticker_upper)
        except Exception:
            logger.exception("Invesco: failed to parse CSV for %s", ticker_upper)
            return []

    def _parse_csv(self, text: str, ticker: str) -> list[dict[str, Any]]:
        """Parse Invesco CSV text into normalized holdings list."""
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            logger.warning("Invesco: empty CSV for %s", ticker)
            return []

        headers = list(reader.fieldnames)

        col_ticker = _find_column(headers, _COLUMN_ALIASES["ticker"])
        col_name = _find_column(headers, _COLUMN_ALIASES["name"])
        col_weight = _find_column(headers, _COLUMN_ALIASES["weight_pct"])
        col_shares = _find_column(headers, _COLUMN_ALIASES["shares"])
        col_market_value = _find_column(headers, _COLUMN_ALIASES["market_value"])

        if col_ticker is None and col_name is None:
            logger.warning(
                "Invesco: could not identify ticker or name columns for %s. Headers: %s",
                ticker,
                headers,
            )
            return []

        # First pass: collect all raw weight values to detect format
        raw_rows: list[dict[str, str]] = []
        raw_weights: list[float] = []

        for row in reader:
            raw_rows.append(row)
            if col_weight:
                w = _safe_float(row.get(col_weight))
                if w is not None and w > 0:
                    raw_weights.append(w)

        # Detect weight format: if total of all weights is close to 1.0 (or max < 1),
        # they are decimal fractions; otherwise they are already percentages
        is_decimal = False
        if raw_weights:
            total = sum(raw_weights)
            max_weight = max(raw_weights)
            # Decimal format: total near 1.0 or all values <= 1.0
            if total <= 1.5 or max_weight <= 1.0:
                is_decimal = True

        # Second pass: build holdings with normalized weights
        holdings: list[dict[str, Any]] = []

        for row in raw_rows:
            holding_ticker = ""
            if col_ticker:
                holding_ticker = row.get(col_ticker, "").strip()

            holding_name = ""
            if col_name:
                holding_name = row.get(col_name, "").strip()

            if not holding_ticker and not holding_name:
                continue

            weight = _safe_float(row.get(col_weight)) if col_weight else None
            if weight is not None and is_decimal:
                weight = weight * 100.0

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

        logger.info("Invesco: parsed %d holdings for %s", len(holdings), ticker)
        return holdings

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> InvescoClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
