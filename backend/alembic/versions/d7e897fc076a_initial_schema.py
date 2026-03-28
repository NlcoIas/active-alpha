"""initial schema

Revision ID: d7e897fc076a
Revises:
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d7e897fc076a"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Benchmarks (no FKs, create first)
    op.create_table(
        "benchmarks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("ticker", sa.String(10), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("index_name", sa.String(255), nullable=True),
        sa.Column("constituent_count", sa.Integer, nullable=True),
        sa.Column("last_holdings_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Funds (FK to benchmarks)
    op.create_table(
        "funds",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("ticker", sa.String(10), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("issuer", sa.String(100), nullable=True),
        sa.Column("type", sa.String(20), nullable=False, server_default="transparent"),
        sa.Column("asset_class", sa.String(20), nullable=False, server_default="equity"),
        sa.Column("benchmark_id", sa.String(32), sa.ForeignKey("benchmarks.id"), nullable=True),
        sa.Column("aum", sa.Numeric(16, 2), nullable=True),
        sa.Column("expense_ratio", sa.Numeric(5, 4), nullable=True),
        sa.Column("inception_date", sa.Date, nullable=True),
        sa.Column("data_source", sa.String(50), nullable=True),
        sa.Column("last_holdings_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Holdings snapshots
    op.create_table(
        "holdings_snapshots",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("fund_id", sa.String(32), sa.ForeignKey("funds.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("asset_type", sa.String(20), nullable=False, server_default="equity"),
        sa.Column("weight_pct", sa.Numeric(8, 5), nullable=False),
        sa.Column("shares", sa.Numeric(16, 4), nullable=True),
        sa.Column("market_value", sa.Numeric(16, 2), nullable=True),
        sa.Column("is_stale", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("source", sa.String(20), nullable=False, server_default="fmp"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fund_id", "snapshot_date", "ticker", name="uq_holdings_fund_date_ticker"),
    )

    # Benchmark holdings
    op.create_table(
        "benchmark_holdings",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("benchmark_id", sa.String(32), sa.ForeignKey("benchmarks.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("weight_pct", sa.Numeric(8, 5), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="fmp"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("benchmark_id", "snapshot_date", "ticker", name="uq_benchmark_bench_date_ticker"),
    )

    # Deviations
    op.create_table(
        "deviations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("fund_id", sa.String(32), sa.ForeignKey("funds.id"), nullable=False),
        sa.Column("benchmark_id", sa.String(32), sa.ForeignKey("benchmarks.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("etf_weight_pct", sa.Numeric(8, 5), nullable=True),
        sa.Column("benchmark_weight_pct", sa.Numeric(8, 5), nullable=True),
        sa.Column("deviation_pct", sa.Numeric(8, 5), nullable=False),
        sa.Column("abs_deviation_pct", sa.Numeric(8, 5), nullable=False),
        sa.Column("deviation_rank", sa.Integer, nullable=True),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fund_id", "benchmark_id", "snapshot_date", "ticker", name="uq_deviations_fund_bench_date_ticker"),
    )

    # Stock prices
    op.create_table(
        "stock_prices",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("price_date", sa.Date, nullable=False),
        sa.Column("open_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("high_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("low_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("adj_close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="fmp"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ticker", "price_date", name="uq_prices_ticker_date"),
    )

    # Pipeline runs
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("target_date", sa.Date, nullable=False),
        sa.Column("funds_attempted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("funds_succeeded", sa.Integer, nullable=False, server_default="0"),
        sa.Column("funds_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("holdings_rows_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deviations_rows_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("api_calls_made", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Numeric(8, 2), nullable=True),
        sa.Column("error_log", postgresql.JSONB, nullable=True),
        sa.Column("skipped_tickers", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Ticker mappings
    op.create_table(
        "ticker_mappings",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("old_ticker", sa.String(10), nullable=False),
        sa.Column("new_ticker", sa.String(10), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ticker_mappings")
    op.drop_table("pipeline_runs")
    op.drop_table("stock_prices")
    op.drop_table("deviations")
    op.drop_table("benchmark_holdings")
    op.drop_table("holdings_snapshots")
    op.drop_table("funds")
    op.drop_table("benchmarks")
