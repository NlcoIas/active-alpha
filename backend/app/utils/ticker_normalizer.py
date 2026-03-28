"""Ticker normalization for consistent matching between ETF and benchmark holdings."""

from __future__ import annotations

import re


# Tickers that represent non-equity positions
NON_EQUITY_TICKERS = frozenset({
    "USD", "CASH", "TBILL", "BILL", "REPO", "MARGIN",
    "SWAP", "FUT", "OPT", "WARRANT",
})

# Pattern for warrants, rights, units
NON_EQUITY_SUFFIXES = re.compile(r"\.(WS|RT|U|WT|WTA|WTB)$", re.IGNORECASE)

# Valid US equity ticker pattern
EQUITY_PATTERN = re.compile(r"^[A-Z]{1,5}(-[A-Z]{1,2})?$")

# Broader pattern allowing international
BROAD_PATTERN = re.compile(r"^[A-Z0-9\.\-]{1,12}$")


class TickerNormalizer:
    """Normalizes ticker symbols for consistent matching.

    Key transforms:
    - Uppercase, strip whitespace
    - BRK.B → BRK-B (share class dot to dash)
    - Filter non-equity holdings (USD, CASH, derivatives)
    - Apply manual alias overrides (FB → META)
    """

    def __init__(self, alias_map: dict[str, str] | None = None) -> None:
        self._alias_map: dict[str, str] = alias_map or {}

    def normalize(self, ticker: str) -> str | None:
        """Normalize a ticker. Returns None if non-equity (should be filtered)."""
        if not ticker:
            return None

        cleaned = ticker.strip().upper()

        if not cleaned:
            return None

        # Filter non-equity positions
        if not self.is_equity(cleaned):
            return None

        # Replace dots with dashes for share classes (BRK.B → BRK-B)
        if "." in cleaned and not NON_EQUITY_SUFFIXES.search(cleaned):
            cleaned = cleaned.replace(".", "-")

        # Apply manual alias
        cleaned = self._alias_map.get(cleaned, cleaned)

        return cleaned

    def normalize_batch(self, tickers: list[str]) -> list[str]:
        """Normalize a list of tickers, filtering out non-equity."""
        result = []
        for t in tickers:
            normalized = self.normalize(t)
            if normalized is not None:
                result.append(normalized)
        return result

    def is_equity(self, ticker: str) -> bool:
        """Check if a ticker represents an equity position."""
        cleaned = ticker.strip().upper()

        if cleaned in NON_EQUITY_TICKERS:
            return False

        if NON_EQUITY_SUFFIXES.search(cleaned):
            return False

        # Reject numeric-only (CUSIP fragments)
        if cleaned.isdigit():
            return False

        # Must match some reasonable pattern
        return bool(BROAD_PATTERN.match(cleaned))

    def resolve_alias(self, ticker: str) -> str:
        """Resolve a ticker alias to its canonical form."""
        cleaned = ticker.strip().upper()
        return self._alias_map.get(cleaned, cleaned)

    def add_alias(self, old_ticker: str, new_ticker: str) -> None:
        """Add a manual alias mapping."""
        self._alias_map[old_ticker.strip().upper()] = new_ticker.strip().upper()
