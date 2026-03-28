"""Multi-source holdings aggregator.

Routes ETF holdings requests to the correct data provider with priority:
1. Provider-specific free clients (ARK, SSGA, Invesco, iShares)
2. FMP API (optional paid fallback)
3. Returns empty if no provider supports the ticker
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.clients.fmp_client import FMPClient

logger = logging.getLogger(__name__)


class HoldingsAggregator:
    """Routes ETF holdings requests to the correct data provider.

    Priority order:
    1. Provider-specific free clients (ARK, SSGA, Invesco, iShares)
    2. FMP API (optional paid fallback)
    3. Returns empty if no provider supports the ticker
    """

    def __init__(self, fmp_client: FMPClient | None = None) -> None:
        from app.clients.ark_client import ARKClient
        from app.clients.invesco_client import InvescoClient
        from app.clients.ishares_client import ISharesClient
        from app.clients.ssga_client import SSGAClient

        self._providers = [
            ARKClient(),
            SSGAClient(),
            InvescoClient(),
            ISharesClient(),
        ]
        self._fmp = fmp_client
        self._api_calls = 0

    @property
    def api_calls_made(self) -> int:
        """Total API calls across all providers."""
        total = self._api_calls
        if self._fmp:
            total += self._fmp.api_calls_made
        return total

    def get_provider_name(self, ticker: str) -> str:
        """Get which provider will handle this ticker."""
        for provider in self._providers:
            if provider.supports(ticker):
                return provider.__class__.__name__
        if self._fmp:
            return "FMPClient"
        return "none"

    async def fetch_holdings(
        self, ticker: str, target_date: date | None = None
    ) -> list[dict]:
        """Fetch holdings from the best available provider.

        Tries free providers first (by checking supports()),
        falls back to FMP if configured.

        Returns:
            List of dicts with keys: ticker, name, weight_pct, shares, market_value
        """
        # Try free providers first
        for provider in self._providers:
            if provider.supports(ticker):
                provider_name = provider.__class__.__name__
                self._api_calls += 1
                try:
                    result = await provider.fetch_holdings(ticker)
                    if result:  # Non-empty = success
                        logger.info(
                            "Fetched %d holdings for %s from %s",
                            len(result),
                            ticker,
                            provider_name,
                        )
                        return result
                    # If empty, fall through to try next provider or FMP
                    logger.warning(
                        "Empty result from %s for %s, trying next provider",
                        provider_name,
                        ticker,
                    )
                except Exception:
                    logger.exception(
                        "Error fetching %s from %s, trying next provider",
                        ticker,
                        provider_name,
                    )

        # Fall back to FMP if available
        if self._fmp:
            logger.info("Falling back to FMP for %s", ticker)
            return await self._fmp.get_etf_holdings(ticker, target_date)

        logger.warning("No provider available for %s", ticker)
        return []

    async def close(self) -> None:
        """Close all provider clients."""
        for provider in self._providers:
            try:
                await provider.close()
            except Exception:
                logger.exception(
                    "Error closing %s", provider.__class__.__name__
                )
        if self._fmp:
            await self._fmp.close()
