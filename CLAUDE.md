# Active Alpha — Project CLAUDE.md

> Active ETF Deviation Tracker & Backtesting Platform
> Extends: `../../CLAUDE.md` (Software Factory root)

## Project Type

Full Stack (FastAPI + Next.js + PostgreSQL + Redis)

## Stack

### Backend (FastAPI)

```
Framework:     FastAPI + Pydantic v2
Database:      PostgreSQL (async SQLAlchemy + Alembic migrations)
Cache:         Redis (backtest result cache, rate limiting)
Scheduler:     APScheduler (daily pipeline) or cron
Data:          Pandas + NumPy for computation
HTTP client:   httpx (async, for API calls)
Task queue:    Celery + Redis (for async backtest computation)
Test runner:   pytest + httpx
```

### Frontend (Next.js)

```
Framework:     Next.js 15+ (App Router)
UI:            shadcn/ui + Tailwind CSS
Charts:        TradingView Lightweight Charts
Tables:        TanStack Table
State:         Zustand
Forms:         React Hook Form + Zod
Test runner:   Vitest + Playwright
```

### Infrastructure

```
Deploy:        Coolify on Proxmox VM
Tunnel:        Cloudflare Tunnel → alpha.nicolasschaerer.ch
Database:      PostgreSQL (Docker container via Coolify)
Cache:         Redis (Docker container via Coolify)
```

## Architecture

```
projects/active-alpha/
  BRIEF.md                    # Full product spec
  CLAUDE.md                   # This file
  docs/
    ARCHITECTURE.md           # Living architecture spec (auto-validated)
  backend/
    app/
      main.py                 # FastAPI app entry point
      config.py               # Settings via pydantic-settings
      database.py             # Async SQLAlchemy engine + session
      models/                 # SQLAlchemy ORM models
        __init__.py
        fund.py               # Fund, Benchmark models
        holdings.py           # HoldingsSnapshot, BenchmarkHoldings
        deviation.py          # Deviation model
        price.py              # StockPrice model
        backtest.py           # BacktestResult cache model
      schemas/                # Pydantic request/response schemas
        __init__.py
        fund.py
        holdings.py
        deviation.py
        backtest.py
      routers/                # API route handlers
        __init__.py
        funds.py              # /api/v1/funds
        holdings.py           # /api/v1/holdings
        deviations.py         # /api/v1/deviations
        backtests.py          # /api/v1/backtests
        health.py             # /api/v1/health
      services/               # Business logic
        __init__.py
        fmp_client.py         # FMP API client
        holdings_fetcher.py   # Fetch + normalize holdings
        deviation_calculator.py # Compute deviations
        backtest_engine.py    # Backtest simulation
        price_fetcher.py      # Stock price data
      tasks/                  # Scheduled jobs
        __init__.py
        daily_pipeline.py     # Main daily pipeline (7am ET)
        backfill.py           # Historical data backfill
      migrations/             # Alembic migrations
    tests/
      __init__.py
      conftest.py
      test_deviation_calculator.py
      test_fmp_client.py
      test_pipeline.py
      test_api.py
    requirements.txt
    Dockerfile
    alembic.ini
    alembic/
  frontend/                   # Next.js app (Phase 3+)
  scripts/
    seed.py                   # Seed initial fund registry
    backfill.py               # Run historical backfill
  docker-compose.yml          # FastAPI + PostgreSQL + Redis
  Dockerfile                  # Frontend Dockerfile (Phase 3+)
```

## Build Phases

### Phase 1: Data Pipeline + Core Backend (current)

- Database schema + Alembic migrations
- Fund registry (seed top 50 active equity ETFs + 5 benchmarks)
- FMP API integration (daily holdings fetch)
- Benchmark holdings fetcher
- Deviation calculator
- Daily scheduled pipeline (7am ET)
- Health check + logging
- Core API endpoints: /funds, /holdings, /deviations
- Tests for pipeline, deviation calc, API

### Phase 2: Backtesting Engine

### Phase 3: Frontend Dashboard

### Phase 4: Backtest Lab UI

### Phase 5: Scale + Polish

### Phase 6: Future / Monetization

## Key Rules

- All work inside `projects/active-alpha/` — only exception is appending to `knowledge/`
- Read `knowledge/stack/api/fastapi.md` before writing FastAPI code
- Literal routes BEFORE parameterized routes (FastAPI matches top-to-bottom)
- All monetary values in cents (integer) — never floating point
- Database migrations MUST run before first deploy
- Seed script reads DATABASE_URL from env — never hardcode localhost
- Rate limit all public endpoints
- Normalize enum values in the API schema layer
- Never expose internal IDs, password hashes, or tokens
- Test everything: pipeline, deviation calc, API endpoints, edge cases
