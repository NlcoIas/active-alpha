"""Core backtesting engine for Active Alpha deviation-based strategies."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, engine
from app.models.deviation import Deviation
from app.models.fund import Fund
from app.schemas.backtest import (
    BacktestConfigSchema,
    BacktestMetrics,
    BacktestResultSchema,
    EquityCurvePoint,
    MonthlyReturn,
)
from app.services.price_service import PriceService

logger = logging.getLogger(__name__)

# Annualization factor (trading days per year)
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.04  # ~4% annual risk-free rate


class BacktestEngine:
    """Runs deviation-based backtests using historical deviation and price data.

    The strategy:
    1. At each rebalance date, pick the top N overweighted stocks across tracked funds.
    2. Weight them equally or by deviation magnitude.
    3. Hold for the holding period, then rebalance.
    4. Track portfolio value and compute performance metrics.
    """

    def __init__(self) -> None:
        pass

    async def run_backtest(self, config: BacktestConfigSchema) -> BacktestResultSchema:
        """Execute a full backtest simulation.

        Args:
            config: Backtest configuration parameters.

        Returns:
            BacktestResultSchema with equity curve and performance metrics.
        """
        logger.info("Starting backtest with config: %s", config.model_dump())

        async with SessionLocal() as db:
            # 1. Determine date range
            end_date = date.today()
            start_date = date(
                end_date.year - config.lookback_years,
                end_date.month,
                end_date.day,
            )

            # 2. Get deviation data
            deviations_df = await self._get_deviations(
                db, start_date, end_date, config.fund_tickers, config.min_deviation_pct
            )

            if deviations_df.empty:
                logger.warning("No deviation data found for backtest period")
                return self._empty_result(config)

            # 3. Get all unique tickers from deviations + benchmark
            stock_tickers = list(deviations_df["ticker"].unique())
            all_tickers = stock_tickers + [config.benchmark_ticker]

            # 4. Get/fetch stock prices
            price_service = PriceService(db)
            prices_df = await price_service.ensure_prices(
                all_tickers, start_date, end_date
            )

            if prices_df.empty:
                logger.warning("No price data available for backtest")
                return self._empty_result(config)

            # 5. Run the simulation
            result = self._simulate(config, deviations_df, prices_df)

        return result

    async def _get_deviations(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        fund_tickers: list[str] | None,
        min_deviation_pct: float,
    ) -> pd.DataFrame:
        """Query deviation data from the database."""
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "min_deviation": min_deviation_pct,
        }

        fund_filter = ""
        if fund_tickers:
            fund_filter = "AND f.ticker = ANY(:fund_tickers)"
            params["fund_tickers"] = fund_tickers

        query = text(f"""
            SELECT
                d.snapshot_date,
                d.ticker,
                f.ticker AS fund_ticker,
                d.deviation_pct,
                d.abs_deviation_pct,
                d.direction,
                d.etf_weight_pct
            FROM deviations d
            JOIN funds f ON d.fund_id = f.id
            WHERE d.snapshot_date >= :start_date
              AND d.snapshot_date <= :end_date
              AND d.abs_deviation_pct >= :min_deviation
              AND d.direction = 'overweight'
              {fund_filter}
            ORDER BY d.snapshot_date, d.abs_deviation_pct DESC
        """)

        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(
            rows,
            columns=[
                "snapshot_date", "ticker", "fund_ticker",
                "deviation_pct", "abs_deviation_pct", "direction",
                "etf_weight_pct",
            ],
        )

    def _simulate(
        self,
        config: BacktestConfigSchema,
        deviations_df: pd.DataFrame,
        prices_df: pd.DataFrame,
    ) -> BacktestResultSchema:
        """Run the portfolio simulation using pandas/numpy."""
        # Convert price data to a pivot table: date x ticker -> adj_close
        prices_df["adj_close"] = prices_df["adj_close"].astype(float)
        prices_df["price_date"] = pd.to_datetime(prices_df["price_date"])

        price_pivot = prices_df.pivot_table(
            index="price_date", columns="ticker", values="adj_close", aggfunc="last"
        )
        price_pivot = price_pivot.sort_index()

        # Calculate daily returns for all tickers
        returns = price_pivot.pct_change().fillna(0)

        # Get benchmark returns
        benchmark_ticker = config.benchmark_ticker
        if benchmark_ticker not in returns.columns:
            logger.warning(
                "Benchmark %s not found in price data, using zero returns",
                benchmark_ticker,
            )
            benchmark_returns = pd.Series(0.0, index=returns.index)
        else:
            benchmark_returns = returns[benchmark_ticker]

        # Generate rebalance dates
        deviation_dates = sorted(deviations_df["snapshot_date"].unique())
        trading_dates = sorted(price_pivot.index)

        if not trading_dates:
            return self._empty_result(config)

        rebalance_dates = self._get_rebalance_dates(
            trading_dates, config.rebalance_frequency
        )

        if not rebalance_dates:
            return self._empty_result(config)

        # Simulate portfolio
        portfolio_value = 1.0
        benchmark_value = 1.0
        equity_curve: list[dict] = []
        trade_results: list[float] = []
        total_trades = 0
        total_turnover = 0.0
        tx_cost_pct = config.transaction_cost_bps / 10000.0

        current_weights: dict[str, float] = {}
        last_rebalance_idx = 0

        for i, trade_date in enumerate(trading_dates):
            trade_date_val = trade_date.date() if hasattr(trade_date, "date") else trade_date

            # Check if we should rebalance
            should_rebalance = trade_date in rebalance_dates

            if should_rebalance:
                # Find the most recent deviation data up to this date
                available_devs = deviations_df[
                    deviations_df["snapshot_date"] <= trade_date_val
                ]

                if available_devs.empty:
                    continue

                # Use the most recent deviation snapshot
                latest_dev_date = available_devs["snapshot_date"].max()
                latest_devs = available_devs[
                    available_devs["snapshot_date"] == latest_dev_date
                ]

                # Pick top N stocks by average deviation across funds
                if config.direction in ("long", "long_short"):
                    top_picks = (
                        latest_devs[latest_devs["deviation_pct"] > 0]
                        .groupby("ticker")
                        .agg(
                            avg_deviation=("deviation_pct", "mean"),
                            fund_count=("fund_ticker", "nunique"),
                        )
                        .sort_values("avg_deviation", ascending=False)
                        .head(config.top_n)
                    )
                else:
                    top_picks = pd.DataFrame()

                # Filter tickers that exist in price data
                valid_tickers = [
                    t for t in top_picks.index if t in returns.columns
                ]

                if not valid_tickers:
                    continue

                # Calculate new weights
                new_weights = self._calculate_weights(
                    valid_tickers, top_picks, config.weighting
                )

                # Calculate turnover
                turnover = self._calculate_turnover(current_weights, new_weights)
                total_turnover += turnover

                # Count trades
                changed_positions = set(new_weights.keys()) ^ set(current_weights.keys())
                for t in new_weights:
                    if t in current_weights and abs(new_weights[t] - current_weights[t]) > 0.001:
                        changed_positions.add(t)
                trades_this_rebalance = len(changed_positions)
                total_trades += trades_this_rebalance

                # Apply transaction costs
                portfolio_value *= (1.0 - turnover * tx_cost_pct)

                current_weights = new_weights
                last_rebalance_idx = i

            # Calculate daily portfolio return
            daily_return = 0.0
            for ticker, weight in current_weights.items():
                if ticker in returns.columns:
                    ticker_return = returns[ticker].iloc[i] if i < len(returns) else 0.0
                    if config.direction == "short":
                        daily_return -= weight * ticker_return
                    else:
                        daily_return += weight * ticker_return

            # Update portfolio and benchmark values
            portfolio_value *= (1.0 + daily_return)
            bm_ret = benchmark_returns.iloc[i] if i < len(benchmark_returns) else 0.0
            benchmark_value *= (1.0 + bm_ret)

            # Track trade results for hit rate calculation
            if should_rebalance and i > 0:
                trade_results.append(daily_return)

            # Record equity curve (sample every 5th day to keep response size manageable)
            if i % 5 == 0 or i == len(trading_dates) - 1:
                equity_curve.append({
                    "date": trade_date_val,
                    "value": round(portfolio_value, 6),
                    "benchmark_value": round(benchmark_value, 6),
                })

        # Calculate metrics
        portfolio_returns = self._calculate_portfolio_returns(equity_curve)
        metrics = self._calculate_metrics(
            portfolio_returns, trade_results, total_trades, total_turnover,
            len(rebalance_dates), portfolio_value, len(trading_dates),
        )

        # Calculate monthly returns
        monthly_returns = self._calculate_monthly_returns(equity_curve)

        return BacktestResultSchema(
            config=config,
            metrics=metrics,
            equity_curve=[
                EquityCurvePoint(
                    date=p["date"],
                    value=p["value"],
                    benchmark_value=p["benchmark_value"],
                )
                for p in equity_curve
            ],
            monthly_returns=monthly_returns,
        )

    def _get_rebalance_dates(
        self,
        trading_dates: list,
        frequency: str,
    ) -> list:
        """Generate rebalance dates based on frequency."""
        if not trading_dates:
            return []

        if frequency == "daily":
            return trading_dates

        rebalance_dates = []
        prev_period = None

        for td in trading_dates:
            td_date = td.date() if hasattr(td, "date") else td

            if frequency == "weekly":
                period = td_date.isocalendar()[1]  # week number
            elif frequency == "monthly":
                period = td_date.month
            else:
                period = td_date.month

            if prev_period is not None and period != prev_period:
                rebalance_dates.append(td)

            prev_period = period

        return rebalance_dates

    def _calculate_weights(
        self,
        tickers: list[str],
        top_picks: pd.DataFrame,
        weighting: str,
    ) -> dict[str, float]:
        """Calculate portfolio weights for selected tickers."""
        n = len(tickers)
        if n == 0:
            return {}

        if weighting == "equal":
            weight = 1.0 / n
            return {t: weight for t in tickers}

        # Deviation-weighted
        total_dev = sum(
            float(top_picks.loc[t, "avg_deviation"]) for t in tickers
        )
        if total_dev <= 0:
            weight = 1.0 / n
            return {t: weight for t in tickers}

        return {
            t: float(top_picks.loc[t, "avg_deviation"]) / total_dev
            for t in tickers
        }

    @staticmethod
    def _calculate_turnover(
        old_weights: dict[str, float],
        new_weights: dict[str, float],
    ) -> float:
        """Calculate portfolio turnover as the sum of absolute weight changes."""
        all_tickers = set(old_weights.keys()) | set(new_weights.keys())
        turnover = sum(
            abs(new_weights.get(t, 0.0) - old_weights.get(t, 0.0))
            for t in all_tickers
        )
        return turnover / 2.0  # one-sided turnover

    @staticmethod
    def _calculate_portfolio_returns(equity_curve: list[dict]) -> np.ndarray:
        """Calculate period returns from the equity curve."""
        if len(equity_curve) < 2:
            return np.array([])

        values = np.array([p["value"] for p in equity_curve])
        return np.diff(values) / values[:-1]

    def _calculate_metrics(
        self,
        portfolio_returns: np.ndarray,
        trade_results: list[float],
        total_trades: int,
        total_turnover: float,
        num_rebalances: int,
        final_value: float,
        num_trading_days: int,
    ) -> BacktestMetrics:
        """Compute all backtest performance metrics."""
        # Cumulative return
        cumulative_return = final_value - 1.0

        # Annualized return
        years = max(num_trading_days / TRADING_DAYS_PER_YEAR, 0.01)
        annualized_return = (final_value ** (1.0 / years)) - 1.0 if final_value > 0 else -1.0

        # Sharpe ratio (annualized)
        if len(portfolio_returns) > 1:
            # Scale to approximate daily returns (equity curve is sampled every 5 days)
            excess_returns = portfolio_returns - (RISK_FREE_RATE / TRADING_DAYS_PER_YEAR * 5)
            mean_excess = np.mean(excess_returns)
            std = np.std(portfolio_returns, ddof=1)
            sharpe_ratio = (
                (mean_excess / std) * np.sqrt(TRADING_DAYS_PER_YEAR / 5)
                if std > 0 else 0.0
            )
        else:
            sharpe_ratio = 0.0

        # Sortino ratio (uses downside deviation)
        if len(portfolio_returns) > 1:
            downside = portfolio_returns[portfolio_returns < 0]
            downside_std = np.std(downside, ddof=1) if len(downside) > 1 else 0.001
            excess_mean = np.mean(portfolio_returns) - (RISK_FREE_RATE / TRADING_DAYS_PER_YEAR * 5)
            sortino_ratio = (
                (excess_mean / downside_std) * np.sqrt(TRADING_DAYS_PER_YEAR / 5)
                if downside_std > 0 else 0.0
            )
        else:
            sortino_ratio = 0.0

        # Max drawdown
        if len(portfolio_returns) > 0:
            cumulative = np.cumprod(1 + portfolio_returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = (cumulative - running_max) / running_max
            max_drawdown = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0
        else:
            max_drawdown = 0.0

        # Hit rate (% of positive trade returns)
        if trade_results:
            hits = sum(1 for r in trade_results if r > 0)
            hit_rate = hits / len(trade_results)
        else:
            hit_rate = 0.0

        # Win/loss ratio
        wins = [r for r in trade_results if r > 0]
        losses = [r for r in trade_results if r < 0]
        if wins and losses:
            avg_win = np.mean(wins)
            avg_loss = abs(np.mean(losses))
            win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        else:
            win_loss_ratio = 0.0

        # Average turnover per rebalance
        avg_turnover = total_turnover / max(num_rebalances, 1)

        return BacktestMetrics(
            cumulative_return=round(cumulative_return, 6),
            annualized_return=round(annualized_return, 6),
            sharpe_ratio=round(sharpe_ratio, 4),
            sortino_ratio=round(sortino_ratio, 4),
            max_drawdown=round(max_drawdown, 6),
            hit_rate=round(hit_rate, 4),
            win_loss_ratio=round(win_loss_ratio, 4),
            turnover=round(avg_turnover, 4),
            total_trades=total_trades,
        )

    @staticmethod
    def _calculate_monthly_returns(equity_curve: list[dict]) -> list[MonthlyReturn]:
        """Calculate monthly returns from the equity curve."""
        if len(equity_curve) < 2:
            return []

        monthly: dict[tuple[int, int], list[float]] = {}
        for i in range(1, len(equity_curve)):
            d = equity_curve[i]["date"]
            year, month = d.year, d.month
            prev_val = equity_curve[i - 1]["value"]
            cur_val = equity_curve[i]["value"]
            ret = (cur_val - prev_val) / prev_val if prev_val > 0 else 0.0
            key = (year, month)
            if key not in monthly:
                monthly[key] = []
            monthly[key].append(ret)

        result: list[MonthlyReturn] = []
        for (year, month), rets in sorted(monthly.items()):
            # Compound the period returns within the month
            compounded = 1.0
            for r in rets:
                compounded *= (1.0 + r)
            result.append(MonthlyReturn(
                year=year,
                month=month,
                return_pct=round(compounded - 1.0, 6),
            ))

        return result

    def _empty_result(self, config: BacktestConfigSchema) -> BacktestResultSchema:
        """Return an empty result when no data is available."""
        return BacktestResultSchema(
            config=config,
            metrics=BacktestMetrics(
                cumulative_return=0.0,
                annualized_return=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                hit_rate=0.0,
                win_loss_ratio=0.0,
                turnover=0.0,
                total_trades=0,
            ),
            equity_curve=[],
            monthly_returns=[],
        )
