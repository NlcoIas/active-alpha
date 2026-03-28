"""Holdings data quality validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta


TICKER_PATTERN = re.compile(r"^[A-Z0-9\.\-]{1,12}$")


@dataclass
class ValidationResult:
    is_valid: bool
    is_stale: bool
    weight_sum: float
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)


class HoldingsValidator:
    """Validates holdings snapshot data quality."""

    def validate_snapshot(
        self,
        fund_ticker: str,
        snapshot_date: date,
        rows: list[dict],
        expected_date: date | None = None,
    ) -> ValidationResult:
        """Validate a holdings snapshot. Returns ValidationResult with errors/warnings."""
        errors: list[str] = []
        warnings: list[str] = []

        # Empty holdings
        if not rows:
            errors.append(f"Empty holdings for {fund_ticker} on {snapshot_date}")
            return ValidationResult(
                is_valid=False,
                is_stale=False,
                weight_sum=0.0,
                errors=errors,
                quality_flags=errors,
            )

        # Weight sum check
        weight_sum, weight_flags = self.check_weight_sum(rows)
        warnings.extend(weight_flags)

        if weight_sum < 50.0:
            errors.append(
                f"Weight sum {weight_sum:.2f}% < 50% for {fund_ticker} — likely partial data"
            )

        # Individual row validation
        for row in rows:
            ticker = row.get("ticker", "")
            weight = row.get("weight_pct")

            if not ticker or not TICKER_PATTERN.match(ticker):
                errors.append(f"Invalid ticker format: '{ticker}'")

            if weight is not None and (weight < -5.0 or weight > 150.0):
                warnings.append(
                    f"Unusual weight {weight:.2f}% for {ticker} in {fund_ticker}"
                )

        # Staleness check
        is_stale = self.check_staleness(
            snapshot_date, expected_date or date.today()
        )
        if is_stale:
            warnings.append(
                f"Data for {fund_ticker} is stale: snapshot_date={snapshot_date}"
            )

        all_flags = errors + warnings
        return ValidationResult(
            is_valid=len(errors) == 0,
            is_stale=is_stale,
            weight_sum=weight_sum,
            errors=errors,
            warnings=warnings,
            quality_flags=all_flags,
        )

    def check_weight_sum(self, rows: list[dict]) -> tuple[float, list[str]]:
        """Check if weight percentages sum to a reasonable value."""
        flags: list[str] = []
        weight_sum = sum(
            float(r.get("weight_pct", 0) or 0)
            for r in rows
        )

        if weight_sum < 85.0:
            flags.append(f"Low weight sum: {weight_sum:.2f}% (possible cash/derivative gap)")
        elif weight_sum > 115.0:
            flags.append(f"High weight sum: {weight_sum:.2f}% (leveraged fund or data error)")

        return weight_sum, flags

    def check_staleness(
        self, snapshot_date: date, expected_date: date
    ) -> bool:
        """Check if data is stale (more than 3 business days old)."""
        delta = (expected_date - snapshot_date).days
        return delta > 5  # 5 calendar days ≈ 3 business days
