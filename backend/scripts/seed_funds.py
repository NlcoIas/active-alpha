"""Seed the fund universe with initial ETFs and benchmarks.

Usage: python -m scripts.seed_funds
Requires DATABASE_URL environment variable.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Benchmark, Fund
from app.models.base import generate_cuid

# Benchmarks to seed
BENCHMARKS = [
    {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "index_name": "S&P 500", "constituent_count": 503},
    {"ticker": "QQQ", "name": "Invesco QQQ Trust", "index_name": "Nasdaq-100", "constituent_count": 101},
    {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "index_name": "Russell 2000", "constituent_count": 1979},
    {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "index_name": "CRSP US Total Market", "constituent_count": 3636},
]

# Initial active equity ETFs with benchmark assignments
# Format: (ticker, name, issuer, benchmark_ticker)
FUNDS = [
    # ARK Invest
    ("ARKK", "ARK Innovation ETF", "ARK Invest", "SPY"),
    ("ARKW", "ARK Next Generation Internet ETF", "ARK Invest", "QQQ"),
    ("ARKG", "ARK Genomic Revolution ETF", "ARK Invest", "SPY"),
    ("ARKF", "ARK Fintech Innovation ETF", "ARK Invest", "SPY"),
    ("ARKQ", "ARK Autonomous Tech & Robotics ETF", "ARK Invest", "SPY"),
    # JPMorgan
    ("JEPQ", "JPMorgan Nasdaq Equity Premium Income ETF", "JPMorgan", "QQQ"),
    ("JEPI", "JPMorgan Equity Premium Income ETF", "JPMorgan", "SPY"),
    ("JGRO", "JPMorgan Active Growth ETF", "JPMorgan", "SPY"),
    ("JVAL", "JPMorgan Active Value ETF", "JPMorgan", "SPY"),
    # Fidelity
    ("FBCG", "Fidelity Blue Chip Growth ETF", "Fidelity", "SPY"),
    ("FBCV", "Fidelity Blue Chip Value ETF", "Fidelity", "SPY"),
    ("FMAG", "Fidelity Magellan ETF", "Fidelity", "SPY"),
    ("FDMO", "Fidelity Momentum Factor ETF", "Fidelity", "SPY"),
    # Capital Group (American Funds)
    ("CGGO", "Capital Group Growth ETF", "Capital Group", "SPY"),
    ("CGDV", "Capital Group Dividend Value ETF", "Capital Group", "SPY"),
    ("CGGR", "Capital Group Global Growth Equity ETF", "Capital Group", "SPY"),
    # T. Rowe Price
    ("TCHP", "T. Rowe Price Blue Chip Growth ETF", "T. Rowe Price", "SPY"),
    ("TDVG", "T. Rowe Price Dividend Growth ETF", "T. Rowe Price", "SPY"),
    ("TGRW", "T. Rowe Price Growth Stock ETF", "T. Rowe Price", "SPY"),
    # Dimensional
    ("DFAC", "Dimensional U.S. Core Equity 2 ETF", "Dimensional", "SPY"),
    ("DFAS", "Dimensional U.S. Small Cap ETF", "Dimensional", "IWM"),
    ("DFAT", "Dimensional U.S. Targeted Value ETF", "Dimensional", "IWM"),
    ("DFAU", "Dimensional US Equity ETF", "Dimensional", "VTI"),
    # Avantis
    ("AVUV", "Avantis U.S. Small Cap Value ETF", "Avantis", "IWM"),
    ("AVLV", "Avantis U.S. Large Cap Value ETF", "Avantis", "SPY"),
    ("AVES", "Avantis U.S. Equity ETF", "Avantis", "SPY"),
    # BlackRock / iShares
    ("IBLC", "iShares Blockchain & Tech ETF", "BlackRock", "QQQ"),
    # Invesco
    ("QGRW", "Invesco Next Gen 100 ETF", "Invesco", "QQQ"),
    # Other notable active ETFs
    ("DIVO", "Amplify CWP Enhanced Dividend Income ETF", "Amplify", "SPY"),
    ("COWZ", "Pacer US Cash Cows 100 ETF", "Pacer", "SPY"),
    ("GARP", "iShares MSCI USA Quality GARP ETF", "BlackRock", "SPY"),
    ("MOAT", "VanEck Morningstar Wide Moat ETF", "VanEck", "SPY"),
    ("QUAL", "iShares MSCI USA Quality Factor ETF", "BlackRock", "SPY"),
    ("DGRW", "WisdomTree U.S. Quality Dividend Growth Fund", "WisdomTree", "SPY"),
    ("FTEC", "Fidelity MSCI Information Technology ETF", "Fidelity", "QQQ"),
    ("VIG", "Vanguard Dividend Appreciation ETF", "Vanguard", "SPY"),
    ("SCHD", "Schwab U.S. Dividend Equity ETF", "Schwab", "SPY"),
    ("DFUV", "Dimensional US Marketwide Value ETF", "Dimensional", "SPY"),
    ("DGRO", "iShares Core Dividend Growth ETF", "BlackRock", "SPY"),
    ("NOBL", "ProShares S&P 500 Dividend Aristocrats ETF", "ProShares", "SPY"),
    ("VONG", "Vanguard Russell 1000 Growth ETF", "Vanguard", "SPY"),
    ("VONV", "Vanguard Russell 1000 Value ETF", "Vanguard", "SPY"),
    ("IUSV", "iShares Core S&P US Value ETF", "BlackRock", "SPY"),
    ("IUSG", "iShares Core S&P US Growth ETF", "BlackRock", "SPY"),
    ("SPGP", "Invesco S&P 500 GARP ETF", "Invesco", "SPY"),
    ("JMOM", "JPMorgan U.S. Momentum Factor ETF", "JPMorgan", "SPY"),
    ("MTUM", "iShares MSCI USA Momentum Factor ETF", "BlackRock", "SPY"),
    ("VLUE", "iShares MSCI USA Value Factor ETF", "BlackRock", "SPY"),
    ("SIZE", "iShares MSCI USA Size Factor ETF", "BlackRock", "SPY"),
    ("USMV", "iShares MSCI USA Min Vol Factor ETF", "BlackRock", "SPY"),
]


async def seed():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable required")
        sys.exit(1)

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Seed benchmarks
        benchmark_map = {}
        for bm in BENCHMARKS:
            benchmark = Benchmark(
                id=generate_cuid(),
                ticker=bm["ticker"],
                name=bm["name"],
                index_name=bm["index_name"],
                constituent_count=bm["constituent_count"],
            )
            session.add(benchmark)
            benchmark_map[bm["ticker"]] = benchmark.id
            print(f"  + Benchmark: {bm['ticker']} ({bm['name']})")

        await session.flush()

        # Seed funds
        for ticker, name, issuer, bench_ticker in FUNDS:
            fund = Fund(
                id=generate_cuid(),
                ticker=ticker,
                name=name,
                issuer=issuer,
                benchmark_id=benchmark_map.get(bench_ticker),
                data_source="fmp",
            )
            session.add(fund)
            print(f"  + Fund: {ticker} ({name}) → {bench_ticker}")

        await session.commit()
        print(f"\nSeeded {len(BENCHMARKS)} benchmarks and {len(FUNDS)} funds.")


if __name__ == "__main__":
    asyncio.run(seed())
