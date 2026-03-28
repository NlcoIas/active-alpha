"""iShares (BlackRock) ETF holdings client.

Fetches daily holdings CSVs from iShares.com using product IDs.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Mapping of ticker to (product_id, slug) — manually maintained for key ETFs
# Product IDs sourced from ishares.com/us/products/{product_id}/{slug}
ISHARES_PRODUCTS: dict[str, tuple[int, str]] = {
    # ── Core / Broad US equity ──────────────────────────────────────────────
    "IVV": (239726, "ishares-core-sp-500-etf"),
    "ITOT": (239724, "ishares-core-sp-total-us-stock-market-etf"),
    "IJH": (239763, "ishares-core-sp-mid-cap-etf"),
    "IJR": (239774, "ishares-core-sp-small-cap-etf"),
    # ── Russell family ──────────────────────────────────────────────────────
    "IWM": (239710, "ishares-russell-2000-etf"),
    "IWB": (239707, "ishares-russell-1000-etf"),
    "IWF": (239706, "ishares-russell-1000-growth-etf"),
    "IWD": (239708, "ishares-russell-1000-value-etf"),
    "IWR": (239718, "ishares-russell-midcap-etf"),
    "IWS": (239719, "ishares-russell-midcap-value-etf"),
    "IWP": (239717, "ishares-russell-midcap-growth-etf"),
    "IWN": (239712, "ishares-russell-2000-value-etf"),
    "IWO": (239711, "ishares-russell-2000-growth-etf"),
    "IWV": (239714, "ishares-russell-3000-etf"),
    # ── Factor / Smart Beta ─────────────────────────────────────────────────
    "QUAL": (256101, "ishares-msci-usa-quality-factor-etf"),
    "USMV": (239695, "ishares-msci-usa-min-vol-factor-etf"),
    "MTUM": (251614, "ishares-msci-usa-momentum-factor-etf"),
    "VLUE": (251616, "ishares-msci-usa-value-factor-etf"),
    "SIZE": (251615, "ishares-msci-usa-size-factor-etf"),
    # ── Dividend ────────────────────────────────────────────────────────────
    "DGRO": (264623, "ishares-core-dividend-growth-etf"),
    "HDV": (239563, "ishares-core-high-dividend-etf"),
    "DVY": (239500, "ishares-select-dividend-etf"),
    # ── Style ───────────────────────────────────────────────────────────────
    "IUSV": (239715, "ishares-core-sp-us-value-etf"),
    "IUSG": (239713, "ishares-core-sp-us-growth-etf"),
    # ── US Sector ───────────────────────────────────────────────────────────
    "IYW": (239522, "ishares-us-technology-etf"),
    "IYH": (239511, "ishares-us-healthcare-etf"),
    "IYF": (239508, "ishares-us-financials-etf"),
    "IYE": (239507, "ishares-us-energy-etf"),
    "IYR": (239520, "ishares-us-real-estate-etf"),
    "IYC": (239506, "ishares-us-consumer-discretionary-etf"),
    "IYK": (239513, "ishares-us-consumer-staples-etf"),
    "IYJ": (239512, "ishares-us-industrials-etf"),
    "IYZ": (239524, "ishares-us-telecommunications-etf"),
    "IYM": (239515, "ishares-us-basic-materials-etf"),
    # ── Thematic / Industry ─────────────────────────────────────────────────
    "SOXX": (239705, "ishares-semiconductor-etf"),
    "IBB": (239699, "ishares-biotechnology-etf"),
    "IGV": (239700, "ishares-expanded-tech-software-sector-etf"),
    "IHI": (239516, "ishares-us-medical-devices-etf"),
    "ITA": (239502, "ishares-us-aerospace-defense-etf"),
    # ── Fixed Income — US Treasury ──────────────────────────────────────────
    "AGG": (239458, "ishares-core-us-aggregate-bond-etf"),
    "TLT": (239454, "ishares-20-plus-year-treasury-bond-etf"),
    "IEF": (239456, "ishares-7-10-year-treasury-bond-etf"),
    "SHY": (239452, "ishares-1-3-year-treasury-bond-etf"),
    "SHV": (239466, "ishares-short-treasury-bond-etf"),
    "GOVT": (239468, "ishares-us-treasury-bond-etf"),
    "TIP": (239467, "ishares-tips-bond-etf"),
    # ── Fixed Income — Corporate / Credit ───────────────────────────────────
    "LQD": (239566, "ishares-iboxx-investment-grade-corporate-bond-etf"),
    "HYG": (239565, "ishares-iboxx-high-yield-corporate-bond-etf"),
    "USIG": (239460, "ishares-broad-usd-investment-grade-corporate-bond-etf"),
    "EMB": (239572, "ishares-jp-morgan-usd-emerging-markets-bond-etf"),
    "MUB": (239766, "ishares-national-muni-bond-etf"),
    # ── International — Developed ───────────────────────────────────────────
    "EFA": (239623, "ishares-msci-eafe-etf"),
    "IEFA": (244049, "ishares-core-msci-eafe-etf"),
    "IXUS": (244048, "ishares-core-msci-total-international-stock-etf"),
    "EWJ": (239665, "ishares-msci-japan-etf"),
    "EWG": (239649, "ishares-msci-germany-etf"),
    "EWU": (239690, "ishares-msci-united-kingdom-etf"),
    "EWA": (239607, "ishares-msci-australia-etf"),
    "EWC": (239615, "ishares-msci-canada-etf"),
    "EWQ": (239678, "ishares-msci-france-etf"),
    "EWL": (239667, "ishares-msci-switzerland-etf"),
    # ── International — Emerging ────────────────────────────────────────────
    "EEM": (239637, "ishares-msci-emerging-markets-etf"),
    "IEMG": (244050, "ishares-core-msci-emerging-markets-etf"),
    "EWZ": (239612, "ishares-msci-brazil-etf"),
    "EWT": (239689, "ishares-msci-taiwan-etf"),
    "EWY": (239681, "ishares-msci-south-korea-etf"),
    "INDA": (239659, "ishares-msci-india-etf"),
    "MCHI": (239619, "ishares-msci-china-etf"),
}

ISHARES_URL_TEMPLATE = (
    "https://www.ishares.com/us/products/{product_id}/{slug}/"
    "1467271812596.ajax?fileType=csv&fileName={ticker}_holdings&dataType=fund"
)

# Column name aliases for flexible header matching
_COLUMN_ALIASES: dict[str, list[str]] = {
    "ticker": ["ticker", "symbol", "security ticker"],
    "name": ["name", "security name", "description", "holding name"],
    "weight_pct": ["weight (%)", "weight(%)", "weight", "% of net assets"],
    "shares": ["shares", "shares held", "par value", "shares/par amount"],
    "market_value": ["market value", "market value ($)", "value", "notional value"],
}

# Rate-limit: 1 second between requests to respect iShares servers
_REQUEST_DELAY_SECONDS = 1.0


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
    cleaned = value.strip().replace(",", "").replace("$", "").replace("%", "").replace('"', "")
    if not cleaned or cleaned == "-" or cleaned.lower() in ("n/a", "na", "--"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_data_header(lines: list[str]) -> int | None:
    """Find the index of the actual data header row in iShares CSV.

    iShares CSVs have ~9 metadata rows, a blank row, then the data header.
    The data header contains both "Ticker" and "Weight" (or similar).
    """
    for idx, line in enumerate(lines):
        lower = line.lower()
        # Look for a row that has both ticker and weight indicators
        has_ticker = "ticker" in lower
        has_weight = "weight" in lower or "% of" in lower
        has_name = "name" in lower
        if has_ticker and (has_weight or has_name):
            return idx
    return None


class ISharesClient:
    """Client for fetching iShares ETF holdings from BlackRock's public CSV endpoint."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "ActiveAlpha/1.0 (ETF research tool)"},
            follow_redirects=True,
        )
        self._last_request_time: float = 0.0
        self._rate_lock = asyncio.Lock()

    def supports(self, ticker: str) -> bool:
        """Check if this provider can fetch holdings for this ticker."""
        return ticker.upper() in ISHARES_PRODUCTS

    async def fetch_holdings(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch holdings for an iShares ETF.

        Returns list of dicts with keys: ticker, name, weight_pct, shares, market_value.
        Weight_pct is in percentage points (e.g. 7.24 means 7.24%).
        Returns empty list on any error.
        """
        ticker_upper = ticker.upper()
        product = ISHARES_PRODUCTS.get(ticker_upper)
        if product is None:
            logger.warning("iShares: unsupported ticker %s", ticker)
            return []

        product_id, slug = product
        url = ISHARES_URL_TEMPLATE.format(
            product_id=product_id, slug=slug, ticker=ticker_upper
        )

        # Rate limiting: ensure at least 1 second between requests
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < _REQUEST_DELAY_SECONDS:
                await asyncio.sleep(_REQUEST_DELAY_SECONDS - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

        try:
            response = await self._http.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "iShares: HTTP %d fetching %s holdings: %s",
                exc.response.status_code,
                ticker_upper,
                exc,
            )
            return []
        except httpx.HTTPError as exc:
            logger.error(
                "iShares: network error fetching %s holdings: %s", ticker_upper, exc
            )
            return []

        try:
            return self._parse_csv(response.text, ticker_upper)
        except Exception:
            logger.exception("iShares: failed to parse CSV for %s", ticker_upper)
            return []

    def _parse_csv(self, text: str, ticker: str) -> list[dict[str, Any]]:
        """Parse iShares CSV text into normalized holdings list.

        iShares CSVs have metadata rows at the top, a blank line, then the data.
        We scan for the header row containing 'Ticker' and 'Weight'.
        """
        lines = text.splitlines()
        header_idx = _find_data_header(lines)

        if header_idx is None:
            logger.warning(
                "iShares: could not find data header row in CSV for %s", ticker
            )
            return []

        # Rebuild CSV from the header row onward
        data_text = "\n".join(lines[header_idx:])
        reader = csv.DictReader(io.StringIO(data_text))

        if reader.fieldnames is None:
            logger.warning("iShares: empty data section in CSV for %s", ticker)
            return []

        headers = list(reader.fieldnames)

        col_ticker = _find_column(headers, _COLUMN_ALIASES["ticker"])
        col_name = _find_column(headers, _COLUMN_ALIASES["name"])
        col_weight = _find_column(headers, _COLUMN_ALIASES["weight_pct"])
        col_shares = _find_column(headers, _COLUMN_ALIASES["shares"])
        col_market_value = _find_column(headers, _COLUMN_ALIASES["market_value"])

        if col_ticker is None and col_name is None:
            logger.warning(
                "iShares: could not identify ticker or name columns for %s. Headers: %s",
                ticker,
                headers,
            )
            return []

        holdings: list[dict[str, Any]] = []

        for row in reader:
            holding_ticker = ""
            if col_ticker:
                holding_ticker = (row.get(col_ticker) or "").strip()

            holding_name = ""
            if col_name:
                holding_name = (row.get(col_name) or "").strip()

            # Skip empty rows, footer metadata, or rows without identifiers
            if not holding_ticker and not holding_name:
                continue

            # iShares sometimes has a footer section with totals — skip rows
            # where ticker looks like metadata (e.g., starts with numbers or dashes)
            if holding_ticker and not holding_ticker[0].isalpha():
                # Could be a numeric row or separator; only skip if name is also empty
                if not holding_name:
                    continue

            weight = _safe_float(row.get(col_weight)) if col_weight else None
            # iShares weight is already in percentage points (e.g. 7.24)
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

        logger.info("iShares: parsed %d holdings for %s", len(holdings), ticker)
        return holdings

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> ISharesClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
