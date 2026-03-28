"""US market holiday detection. Static list for reliability."""

from __future__ import annotations

from datetime import date, timedelta

# NYSE holidays 2024-2027
# Source: NYSE holiday schedule
_US_MARKET_HOLIDAYS: set[date] = {
    # 2024
    date(2024, 1, 1),    # New Year's Day
    date(2024, 1, 15),   # MLK Day
    date(2024, 2, 19),   # Presidents' Day
    date(2024, 3, 29),   # Good Friday
    date(2024, 5, 27),   # Memorial Day
    date(2024, 6, 19),   # Juneteenth
    date(2024, 7, 4),    # Independence Day
    date(2024, 9, 2),    # Labor Day
    date(2024, 11, 28),  # Thanksgiving
    date(2024, 12, 25),  # Christmas
    # 2025
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # MLK Day
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
    # 2027
    date(2027, 1, 1),    # New Year's Day
    date(2027, 1, 18),   # MLK Day
    date(2027, 2, 15),   # Presidents' Day
    date(2027, 3, 26),   # Good Friday
    date(2027, 5, 31),   # Memorial Day
    date(2027, 6, 18),   # Juneteenth (observed)
    date(2027, 7, 5),    # Independence Day (observed)
    date(2027, 9, 6),    # Labor Day
    date(2027, 11, 25),  # Thanksgiving
    date(2027, 12, 24),  # Christmas (observed)
}


def is_market_holiday(d: date) -> bool:
    """Check if a date is a US market holiday."""
    return d in _US_MARKET_HOLIDAYS


def is_weekend(d: date) -> bool:
    """Check if a date is a weekend (Saturday=5, Sunday=6)."""
    return d.weekday() >= 5


def is_trading_day(d: date) -> bool:
    """Check if a date is a US trading day."""
    return not is_weekend(d) and not is_market_holiday(d)


def previous_trading_day(d: date) -> date:
    """Get the most recent trading day on or before the given date."""
    current = d
    while not is_trading_day(current):
        current -= timedelta(days=1)
    return current


def next_trading_day(d: date) -> date:
    """Get the next trading day on or after the given date."""
    current = d
    while not is_trading_day(current):
        current += timedelta(days=1)
    return current
