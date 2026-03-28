"""Tests for TickerNormalizer."""

import pytest

from app.utils.ticker_normalizer import TickerNormalizer


@pytest.fixture
def normalizer():
    return TickerNormalizer(alias_map={"FB": "META", "TWTR": "X"})


class TestNormalize:
    def test_basic_uppercase(self, normalizer):
        assert normalizer.normalize("aapl") == "AAPL"

    def test_strip_whitespace(self, normalizer):
        assert normalizer.normalize("  MSFT  ") == "MSFT"

    def test_share_class_dot_to_dash(self, normalizer):
        assert normalizer.normalize("BRK.B") == "BRK-B"

    def test_share_class_bf(self, normalizer):
        assert normalizer.normalize("BF.B") == "BF-B"

    def test_already_dash_format(self, normalizer):
        assert normalizer.normalize("BRK-B") == "BRK-B"

    def test_filter_cash(self, normalizer):
        assert normalizer.normalize("USD") is None
        assert normalizer.normalize("CASH") is None
        assert normalizer.normalize("TBILL") is None

    def test_filter_warrants(self, normalizer):
        assert normalizer.normalize("SPAC.WS") is None
        assert normalizer.normalize("ABC.RT") is None

    def test_filter_numeric_only(self, normalizer):
        assert normalizer.normalize("12345") is None

    def test_empty_string(self, normalizer):
        assert normalizer.normalize("") is None

    def test_whitespace_only(self, normalizer):
        assert normalizer.normalize("   ") is None

    def test_alias_resolution(self, normalizer):
        assert normalizer.normalize("FB") == "META"
        assert normalizer.normalize("TWTR") == "X"

    def test_normal_ticker(self, normalizer):
        assert normalizer.normalize("TSLA") == "TSLA"
        assert normalizer.normalize("GOOGL") == "GOOGL"


class TestNormalizeBatch:
    def test_filters_non_equity(self, normalizer):
        tickers = ["AAPL", "USD", "MSFT", "CASH", "TSLA"]
        result = normalizer.normalize_batch(tickers)
        assert result == ["AAPL", "MSFT", "TSLA"]

    def test_normalizes_all(self, normalizer):
        tickers = ["brk.b", "  aapl  ", "FB"]
        result = normalizer.normalize_batch(tickers)
        assert result == ["BRK-B", "AAPL", "META"]


class TestIsEquity:
    def test_standard_tickers(self, normalizer):
        assert normalizer.is_equity("AAPL") is True
        assert normalizer.is_equity("MSFT") is True
        assert normalizer.is_equity("A") is True

    def test_non_equity(self, normalizer):
        assert normalizer.is_equity("USD") is False
        assert normalizer.is_equity("CASH") is False

    def test_warrants(self, normalizer):
        assert normalizer.is_equity("SPAC.WS") is False

    def test_numeric(self, normalizer):
        assert normalizer.is_equity("12345") is False
