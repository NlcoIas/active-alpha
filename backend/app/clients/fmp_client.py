"""Financial Modeling Prep API client with rate limiting and retry."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from time import monotonic
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# FMP field name aliases → canonical names
FIELD_ALIASES: dict[str, list[str]] = {
    "ticker": ["asset", "symbol", "ticker", "holdingsTicker"],
    "name": ["name", "holdingsName", "companyName"],
    "weight_pct": ["weightPercentage", "weight", "percentageValue"],
    "shares": ["sharesNumber", "shares", "holdingsShares"],
    "market_value": ["marketValue", "value", "holdingsValue"],
}


def normalize_holding(raw: dict) -> dict:
    """Map FMP's inconsistent field names to canonical schema."""
    result: dict[str, Any] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in raw and raw[alias] is not None:
                result[canonical] = raw[alias]
                break
    return result


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retry_statuses: set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504}
    )


class RateLimiter:
    """Sliding-window rate limiter with async support."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request slot is available."""
        async with self._lock:
            now = monotonic()
            while self._timestamps and self._timestamps[0] <= now - self._window_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._max_requests:
                sleep_until = self._timestamps[0] + self._window_seconds
                await asyncio.sleep(sleep_until - now)
                now = monotonic()
                while self._timestamps and self._timestamps[0] <= now - self._window_seconds:
                    self._timestamps.popleft()
            self._timestamps.append(monotonic())

    def remaining(self) -> int:
        now = monotonic()
        while self._timestamps and self._timestamps[0] <= now - self._window_seconds:
            self._timestamps.popleft()
        return max(0, self._max_requests - len(self._timestamps))


class FMPClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FMPRateLimitError(FMPClientError):
    pass


class FMPClient:
    """Async FMP API client with rate limiting and retry.

    Usage:
        async with FMPClient(api_key="...") as fmp:
            holdings = await fmp.get_etf_holdings("ARKK")
    """

    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        max_concurrent: int = 5,
        requests_per_minute: int = 250,
        retry_config: RetryConfig | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url or self.BASE_URL
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._rate_limiter = RateLimiter(requests_per_minute, 60.0)
        self._retry_config = retry_config or RetryConfig()
        self._http = httpx.AsyncClient(timeout=timeout)
        self._api_calls = 0

    @property
    def api_calls_made(self) -> int:
        return self._api_calls

    async def __aenter__(self) -> FMPClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def get_etf_holdings(
        self, ticker: str, target_date: date | None = None
    ) -> list[dict]:
        """Fetch ETF holdings. Returns normalized holding dicts."""
        params: dict[str, str] = {}
        if target_date:
            params["date"] = target_date.isoformat()
        raw = await self._request(f"/etf-holder/{ticker}", params)
        if not isinstance(raw, list):
            return []
        return [normalize_holding(h) for h in raw if h]

    async def get_etf_list(self) -> list[dict]:
        """Fetch list of all ETFs."""
        result = await self._request("/etf/list")
        return result if isinstance(result, list) else []

    async def get_etf_info(self, ticker: str) -> dict | None:
        """Fetch ETF profile info."""
        result = await self._request(f"/profile/{ticker}")
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    async def get_stock_price_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[dict]:
        """Fetch historical daily prices."""
        params = {"from": from_date.isoformat(), "to": to_date.isoformat()}
        result = await self._request(
            f"/historical-price-full/{ticker}", params
        )
        if isinstance(result, dict) and "historical" in result:
            return result["historical"]
        return result if isinstance(result, list) else []

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(
        self, endpoint: str, params: dict[str, str] | None = None
    ) -> Any:
        url = f"{self._base_url}{endpoint}"
        request_params = {"apikey": self._api_key, **(params or {})}

        async with self._semaphore:
            return await self._retry_with_backoff(url, request_params)

    async def _retry_with_backoff(
        self, url: str, params: dict[str, str]
    ) -> Any:
        last_error: Exception | None = None
        cfg = self._retry_config

        for attempt in range(cfg.max_retries + 1):
            await self._rate_limiter.acquire()
            self._api_calls += 1

            try:
                response = await self._http.get(url, params=params)

                if response.status_code == 429:
                    raise FMPRateLimitError(
                        "Rate limited by FMP", status_code=429
                    )

                if response.status_code in cfg.retry_statuses:
                    raise FMPClientError(
                        f"FMP returned {response.status_code}",
                        status_code=response.status_code,
                    )

                response.raise_for_status()
                data = response.json()

                if isinstance(data, dict) and "Error Message" in data:
                    raise FMPClientError(data["Error Message"])

                return data

            except (FMPRateLimitError, FMPClientError) as e:
                last_error = e
                if attempt < cfg.max_retries:
                    delay = min(cfg.base_delay * (2**attempt), cfg.max_delay)
                    logger.warning(
                        "FMP request failed (attempt %d/%d): %s. Retrying in %.1fs",
                        attempt + 1, cfg.max_retries + 1, e, delay,
                    )
                    await asyncio.sleep(delay)
                continue

            except httpx.HTTPError as e:
                last_error = FMPClientError(str(e))
                if attempt < cfg.max_retries:
                    delay = min(cfg.base_delay * (2**attempt), cfg.max_delay)
                    logger.warning(
                        "HTTP error (attempt %d/%d): %s. Retrying in %.1fs",
                        attempt + 1, cfg.max_retries + 1, e, delay,
                    )
                    await asyncio.sleep(delay)
                continue

        raise last_error or FMPClientError("Request failed after retries")
