"""Invesco ETF holdings client.

Fetches daily holdings from Invesco's dng-api.invesco.com JSON API.
Uses CUSIP-based lookup (Invesco's new API requires CUSIP, not ticker).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

INVESCO_API_URL = (
    "https://dng-api.invesco.com/cache/v1/accounts/en_US"
    "/shareclasses/{cusip}/holdings/fund"
)

# Mapping of ticker → CUSIP for known Invesco ETFs
INVESCO_CUSIPS: dict[str, str] = {
    # Nasdaq / S&P
    "QQQ": "46090E103",
    "QQQM": "46138G649",
    "RSP": "46137V357",
    # Factor / Smart beta
    "SPHB": "46138E370",
    "SPHQ": "46138E347",
    "SPHD": "46138E362",
    "PRFZ": "46137V753",
    # Equal weight sector
    "RSPT": "46137V845",
    "RSPF": "46137V860",
    "RSPE": "46137V878",
    # S&P 500 GARP
    "SPGP": "46137V266",
    # Other popular
    "PGX": "46138E818",
    "BKLN": "46138G508",
    "PDBC": "46138J101",
    # Next Gen
    "QGRW": "46090G108",
}


class InvescoClient:
    """Client for fetching Invesco ETF holdings from their JSON API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "ActiveAlpha/1.0 (ETF research tool)"},
        )

    def supports(self, ticker: str) -> bool:
        """Check if this provider can fetch holdings for this ticker."""
        return ticker.upper() in INVESCO_CUSIPS

    async def fetch_holdings(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch holdings for an Invesco ETF via JSON API.

        Returns list of dicts with keys: ticker, name, weight_pct, shares, market_value.
        Weight_pct is in percentage points (e.g. 7.24 means 7.24%).
        Returns empty list on any error.
        """
        ticker_upper = ticker.upper()
        cusip = INVESCO_CUSIPS.get(ticker_upper)
        if cusip is None:
            logger.warning("Invesco: no CUSIP for ticker %s", ticker_upper)
            return []

        url = INVESCO_API_URL.format(cusip=cusip)

        try:
            response = await self._http.get(
                url,
                params={"idType": "cusip", "productType": "ETF"},
            )
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
                "Invesco: network error fetching %s holdings: %s",
                ticker_upper,
                exc,
            )
            return []

        try:
            return self._parse_json(response.json(), ticker_upper)
        except Exception:
            logger.exception("Invesco: failed to parse JSON for %s", ticker_upper)
            return []

    def _parse_json(self, data: dict, ticker: str) -> list[dict[str, Any]]:
        """Parse Invesco JSON API response into normalized holdings list."""
        raw_holdings = data.get("holdings", [])
        if not raw_holdings:
            logger.warning("Invesco: no holdings in response for %s", ticker)
            return []

        holdings: list[dict[str, Any]] = []

        for h in raw_holdings:
            holding_ticker = (h.get("ticker") or "").strip()
            holding_name = (h.get("issuerName") or "").strip()

            if not holding_ticker and not holding_name:
                continue

            weight_pct = h.get("percentageOfTotalNetAssets")
            shares = h.get("units")
            market_value = h.get("marketValueBase")

            holdings.append({
                "ticker": holding_ticker,
                "name": holding_name,
                "weight_pct": float(weight_pct) if weight_pct is not None else None,
                "shares": float(shares) if shares is not None else None,
                "market_value": float(market_value) if market_value is not None else None,
            })

        logger.info("Invesco: parsed %d holdings for %s", len(holdings), ticker)
        return holdings

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> InvescoClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
