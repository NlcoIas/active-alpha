"""Tests for FMP client — rate limiter and response normalization."""

import asyncio

import pytest

from app.clients.fmp_client import (
    RateLimiter,
    normalize_holding,
)


class TestNormalizeHolding:
    def test_standard_fmp_response(self):
        raw = {
            "asset": "AAPL",
            "name": "Apple Inc",
            "sharesNumber": 12345678,
            "weightPercentage": 9.45,
            "marketValue": 2345678900,
        }
        result = normalize_holding(raw)
        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc"
        assert result["shares"] == 12345678
        assert result["weight_pct"] == 9.45
        assert result["market_value"] == 2345678900

    def test_alternative_field_names(self):
        raw = {
            "symbol": "MSFT",
            "companyName": "Microsoft Corp",
            "weight": 8.2,
        }
        result = normalize_holding(raw)
        assert result["ticker"] == "MSFT"
        assert result["name"] == "Microsoft Corp"
        assert result["weight_pct"] == 8.2

    def test_missing_optional_fields(self):
        raw = {"asset": "TSLA", "weightPercentage": 5.0}
        result = normalize_holding(raw)
        assert result["ticker"] == "TSLA"
        assert result["weight_pct"] == 5.0
        assert "name" not in result
        assert "shares" not in result

    def test_none_values_skipped(self):
        raw = {"asset": "GOOG", "name": None, "weightPercentage": 3.0}
        result = normalize_holding(raw)
        assert result["ticker"] == "GOOG"
        assert "name" not in result
        assert result["weight_pct"] == 3.0

    def test_empty_dict(self):
        result = normalize_holding({})
        assert result == {}


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=1.0)
        for _ in range(5):
            await limiter.acquire()
        assert limiter.remaining() == 0

    @pytest.mark.asyncio
    async def test_remaining_count(self):
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        assert limiter.remaining() == 10
        await limiter.acquire()
        assert limiter.remaining() == 9

    @pytest.mark.asyncio
    async def test_blocks_when_limit_reached(self):
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        await limiter.acquire()
        await limiter.acquire()
        # Third acquire should block briefly then succeed
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.05  # Should have waited
