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
    # ── SPDR broad / style (newly tracked) ──────────────────────────────────
    ("SPLG", "SPDR Portfolio S&P 500 ETF", "State Street", "SPY"),
    ("SPTM", "SPDR Portfolio S&P 1500 Composite Stock Market ETF", "State Street", "VTI"),
    ("SPMD", "SPDR Portfolio S&P 400 Mid Cap ETF", "State Street", "SPY"),
    ("SPSM", "SPDR Portfolio S&P 600 Small Cap ETF", "State Street", "IWM"),
    ("SPYG", "SPDR Portfolio S&P 500 Growth ETF", "State Street", "SPY"),
    ("SPYV", "SPDR Portfolio S&P 500 Value ETF", "State Street", "SPY"),
    ("SPYD", "SPDR Portfolio S&P 500 High Dividend ETF", "State Street", "SPY"),
    ("RSP", "Invesco S&P 500 Equal Weight ETF", "Invesco", "SPY"),
    ("MDY", "SPDR S&P Midcap 400 ETF Trust", "State Street", "SPY"),
    ("SDY", "SPDR S&P Dividend ETF", "State Street", "SPY"),
    ("DIA", "SPDR Dow Jones Industrial Average ETF Trust", "State Street", "SPY"),
    # ── SPDR Sector SPDRs (newly tracked) ───────────────────────────────────
    ("XLK", "Technology Select Sector SPDR Fund", "State Street", "QQQ"),
    ("XLF", "Financial Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLE", "Energy Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLV", "Health Care Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLI", "Industrial Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLU", "Utilities Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLC", "Communication Services Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLRE", "Real Estate Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLB", "Materials Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLP", "Consumer Staples Select Sector SPDR Fund", "State Street", "SPY"),
    ("XLY", "Consumer Discretionary Select Sector SPDR Fund", "State Street", "SPY"),
    # ── SPDR Industry SPDRs (newly tracked) ─────────────────────────────────
    ("KRE", "SPDR S&P Regional Banking ETF", "State Street", "SPY"),
    ("KBE", "SPDR S&P Bank ETF", "State Street", "SPY"),
    ("XBI", "SPDR S&P Biotech ETF", "State Street", "SPY"),
    ("XHB", "SPDR S&P Homebuilders ETF", "State Street", "SPY"),
    ("XME", "SPDR S&P Metals & Mining ETF", "State Street", "SPY"),
    ("XOP", "SPDR S&P Oil & Gas Exploration & Production ETF", "State Street", "SPY"),
    ("XRT", "SPDR S&P Retail ETF", "State Street", "SPY"),
    ("XAR", "SPDR S&P Aerospace & Defense ETF", "State Street", "SPY"),
    # ── iShares Core / Broad (newly tracked) ────────────────────────────────
    ("IVV", "iShares Core S&P 500 ETF", "BlackRock", "SPY"),
    ("ITOT", "iShares Core S&P Total US Stock Market ETF", "BlackRock", "VTI"),
    ("IJH", "iShares Core S&P Mid-Cap ETF", "BlackRock", "SPY"),
    ("IJR", "iShares Core S&P Small-Cap ETF", "BlackRock", "IWM"),
    ("IXUS", "iShares Core MSCI Total International Stock ETF", "BlackRock", "SPY"),
    # ── iShares Russell mid/small style (newly tracked) ─────────────────────
    ("IWR", "iShares Russell Mid-Cap ETF", "BlackRock", "SPY"),
    ("IWS", "iShares Russell Mid-Cap Value ETF", "BlackRock", "SPY"),
    ("IWP", "iShares Russell Mid-Cap Growth ETF", "BlackRock", "SPY"),
    ("IWN", "iShares Russell 2000 Value ETF", "BlackRock", "IWM"),
    ("IWO", "iShares Russell 2000 Growth ETF", "BlackRock", "IWM"),
    ("IWV", "iShares Russell 3000 ETF", "BlackRock", "VTI"),
    # ── iShares Sector (newly tracked) ──────────────────────────────────────
    ("IYW", "iShares US Technology ETF", "BlackRock", "QQQ"),
    ("IYH", "iShares US Healthcare ETF", "BlackRock", "SPY"),
    ("IYF", "iShares US Financials ETF", "BlackRock", "SPY"),
    ("IYE", "iShares US Energy ETF", "BlackRock", "SPY"),
    ("IYR", "iShares US Real Estate ETF", "BlackRock", "SPY"),
    # ── iShares Thematic / Industry (newly tracked) ─────────────────────────
    ("SOXX", "iShares Semiconductor ETF", "BlackRock", "QQQ"),
    ("IBB", "iShares Biotechnology ETF", "BlackRock", "SPY"),
    ("IGV", "iShares Expanded Tech-Software Sector ETF", "BlackRock", "QQQ"),
    # ── iShares International — Country (newly tracked) ─────────────────────
    ("EWJ", "iShares MSCI Japan ETF", "BlackRock", "SPY"),
    ("EWG", "iShares MSCI Germany ETF", "BlackRock", "SPY"),
    ("EWU", "iShares MSCI United Kingdom ETF", "BlackRock", "SPY"),
    ("EWZ", "iShares MSCI Brazil ETF", "BlackRock", "SPY"),
    # ── iShares Fixed Income (newly tracked) ────────────────────────────────
    ("TLT", "iShares 20+ Year Treasury Bond ETF", "BlackRock", "SPY"),
    ("IEF", "iShares 7-10 Year Treasury Bond ETF", "BlackRock", "SPY"),
    ("SHY", "iShares 1-3 Year Treasury Bond ETF", "BlackRock", "SPY"),
    ("LQD", "iShares iBoxx Investment Grade Corporate Bond ETF", "BlackRock", "SPY"),
    ("HYG", "iShares iBoxx High Yield Corporate Bond ETF", "BlackRock", "SPY"),
    ("GOVT", "iShares US Treasury Bond ETF", "BlackRock", "SPY"),
    ("AGG", "iShares Core US Aggregate Bond ETF", "BlackRock", "SPY"),
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
