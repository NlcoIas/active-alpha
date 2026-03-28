"""Tests for market calendar."""

from datetime import date

from app.utils.market_calendar import (
    is_market_holiday,
    is_trading_day,
    is_weekend,
    next_trading_day,
    previous_trading_day,
)


class TestIsMarketHoliday:
    def test_christmas_2026(self):
        assert is_market_holiday(date(2026, 12, 25)) is True

    def test_thanksgiving_2026(self):
        assert is_market_holiday(date(2026, 11, 26)) is True

    def test_regular_day(self):
        assert is_market_holiday(date(2026, 3, 30)) is False

    def test_mlk_day_2026(self):
        assert is_market_holiday(date(2026, 1, 19)) is True


class TestIsWeekend:
    def test_saturday(self):
        assert is_weekend(date(2026, 3, 28)) is True  # Saturday

    def test_sunday(self):
        assert is_weekend(date(2026, 3, 29)) is True  # Sunday

    def test_monday(self):
        assert is_weekend(date(2026, 3, 30)) is False  # Monday


class TestIsTradingDay:
    def test_regular_weekday(self):
        assert is_trading_day(date(2026, 3, 30)) is True  # Monday

    def test_weekend(self):
        assert is_trading_day(date(2026, 3, 28)) is False  # Saturday

    def test_holiday(self):
        assert is_trading_day(date(2026, 12, 25)) is False  # Christmas


class TestPreviousTradingDay:
    def test_from_weekend(self):
        # Saturday → Friday
        assert previous_trading_day(date(2026, 3, 28)) == date(2026, 3, 27)

    def test_from_monday(self):
        assert previous_trading_day(date(2026, 3, 30)) == date(2026, 3, 30)

    def test_from_holiday(self):
        # Christmas 2026 is Friday → Thursday
        assert previous_trading_day(date(2026, 12, 25)) == date(2026, 12, 24)


class TestNextTradingDay:
    def test_from_friday(self):
        assert next_trading_day(date(2026, 3, 27)) == date(2026, 3, 27)

    def test_from_saturday(self):
        assert next_trading_day(date(2026, 3, 28)) == date(2026, 3, 30)  # Monday
