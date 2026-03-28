"""Tests for HoldingsValidator."""

from datetime import date

import pytest

from app.utils.validation import HoldingsValidator


@pytest.fixture
def validator():
    return HoldingsValidator()


def make_holding(ticker="AAPL", weight=5.0):
    return {"ticker": ticker, "weight_pct": weight}


class TestValidateSnapshot:
    def test_valid_snapshot(self, validator):
        rows = [make_holding("AAPL", 30), make_holding("MSFT", 25), make_holding("GOOGL", 20), make_holding("AMZN", 15), make_holding("TSLA", 10)]
        result = validator.validate_snapshot("ARKK", date(2026, 3, 27), rows)
        assert result.is_valid is True
        assert result.weight_sum == pytest.approx(100.0)
        assert len(result.errors) == 0

    def test_empty_holdings(self, validator):
        result = validator.validate_snapshot("ARKK", date(2026, 3, 27), [])
        assert result.is_valid is False
        assert "Empty holdings" in result.errors[0]

    def test_low_weight_sum_error(self, validator):
        rows = [make_holding("AAPL", 20), make_holding("MSFT", 15)]
        result = validator.validate_snapshot("ARKK", date(2026, 3, 27), rows)
        assert result.is_valid is False  # < 50%
        assert any("< 50%" in e for e in result.errors)

    def test_low_weight_sum_warning(self, validator):
        rows = [make_holding("AAPL", 40), make_holding("MSFT", 35)]
        result = validator.validate_snapshot("ARKK", date(2026, 3, 27), rows)
        assert result.is_valid is True  # 75% is valid but warns
        assert any("Low weight sum" in w for w in result.warnings)

    def test_high_weight_sum_warning(self, validator):
        rows = [make_holding("AAPL", 60), make_holding("MSFT", 60)]
        result = validator.validate_snapshot("ARKK", date(2026, 3, 27), rows)
        assert result.is_valid is True  # 120% is valid (leveraged) but warns
        assert any("High weight sum" in w for w in result.warnings)

    def test_unusual_weight_warning(self, validator):
        rows = [make_holding("AAPL", 160)]  # > 150%
        result = validator.validate_snapshot("ARKK", date(2026, 3, 27), rows)
        assert any("Unusual weight" in w for w in result.warnings)

    def test_invalid_ticker_format(self, validator):
        rows = [{"ticker": "!!!", "weight_pct": 10}]
        result = validator.validate_snapshot("ARKK", date(2026, 3, 27), rows)
        assert any("Invalid ticker" in e for e in result.errors)


class TestCheckStaleness:
    def test_fresh_data(self, validator):
        assert validator.check_staleness(date(2026, 3, 27), date(2026, 3, 28)) is False

    def test_stale_data(self, validator):
        assert validator.check_staleness(date(2026, 3, 20), date(2026, 3, 28)) is True

    def test_same_day(self, validator):
        assert validator.check_staleness(date(2026, 3, 28), date(2026, 3, 28)) is False
