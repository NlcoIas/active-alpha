# Implementation Plan — Active Alpha Phase 1

> Data pipeline, database schema, FMP API integration, deviation calculator, daily pipeline
> Generated: 2026-03-28

## Task Order (by dependency)

### Layer 1: Foundation (no dependencies)

- [ ] **T1: Database models + base** — `models/base.py`, `models/fund.py`, `models/benchmark.py`, `models/holdings_snapshot.py`, `models/benchmark_holding.py`, `models/deviation.py`, `models/stock_price.py`, `models/pipeline_run.py`, `models/ticker_mapping.py`, `database.py`. All SQLAlchemy models with exact types from ARCHITECTURE.md. DeclarativeBase with UUID mixin and timestamp mixin.

- [ ] **T2: Config + settings** — `config.py` with all settings (DB, Redis, FMP API key, pipeline schedule, benchmark tickers). Pydantic v2 `model_config = SettingsConfigDict(...)`.

- [ ] **T3: Alembic migration** — `alembic/` setup with sync engine in `env.py`. Initial migration `001_initial_schema.py` creating all 8 tables with indexes and constraints.

### Layer 2: Utilities (depends on Layer 1)

- [ ] **T4: Ticker normalizer** — `utils/ticker_normalizer.py`. Uppercase, strip, BRK.B→BRK-B, filter non-equity (USD, CASH, TBILL). `normalize()`, `normalize_batch()`, `is_equity()`, `resolve_alias()`.

- [ ] **T5: Bulk upsert helpers** — `utils/bulk_ops.py`. Raw SQL with `ON CONFLICT DO UPDATE` for holdings, benchmark_holdings, deviations, prices. Uses `text()` and `executemany()` via AsyncConnection.

- [ ] **T6: Market calendar** — `utils/market_calendar.py`. US market holiday detection. Static list of NYSE holidays for 2024-2027. `is_market_holiday(date) -> bool`, `next_trading_day(date) -> date`.

- [ ] **T7: Holdings validator** — `utils/validation.py`. `validate_snapshot()` checks weight_sum (warn <85%, error <50%, note >115%), ticker format, date staleness. Returns `ValidationResult` with errors, warnings, quality_flags.

### Layer 3: FMP Client (depends on Layer 2)

- [ ] **T8: FMP API client** — `clients/fmp_client.py`. `RateLimiter` (sliding window, asyncio.Lock), `RetryConfig` (3 retries, exponential backoff, retry on 429/5xx), `FMPClient` (get_etf_holdings, get_etf_list, get_etf_info, get_stock_price_history). Context manager support. FMP field name normalization (asset→ticker, weightPercentage→weight_pct).

### Layer 4: Services (depends on Layers 2-3)

- [ ] **T9: Holdings service** — `services/holdings_service.py`. `fetch_and_store_holdings()` for single fund, `fetch_and_store_batch()` with concurrency control (asyncio.Semaphore). Normalizes via TickerNormalizer, validates via HoldingsValidator, upserts via bulk_ops.

- [ ] **T10: Benchmark service** — `services/benchmark_service.py`. Same pattern as holdings but for benchmarks. `fetch_and_store_benchmark_holdings()`, `fetch_all_benchmarks()`.

- [ ] **T11: Deviation service** — `services/deviation_service.py`. `calculate_deviations()` — SQL FULL OUTER JOIN with ROW_NUMBER() for ranking. `calculate_all_deviations()` iterates active funds. `get_fund_deviations()`, `get_top_deviations_across_funds()`, `get_stock_holders()` for API reads.

- [ ] **T12: Fund service** — `services/fund_service.py`. `list_funds()` with filters, `get_fund()` by ticker, `sync_fund_universe()` from FMP.

### Layer 5: Pipeline (depends on Layer 4)

- [ ] **T13: Pipeline orchestrator** — `services/pipeline_orchestrator.py`. `run_daily_pipeline()` coordinates stages: check holiday → fetch holdings → fetch benchmarks → calculate deviations → record result. Error recovery: per-fund failures logged+skipped, benchmark failure aborts. Creates PipelineRun record at start, updates at completion.

- [ ] **T14: Scheduler** — `scheduler/jobs.py`. APScheduler `AsyncIOScheduler` with CronTrigger(hour=7, timezone="US/Eastern"), `misfire_grace_time=3600`. Registered in app lifespan.

### Layer 6: API (depends on Layers 4-5)

- [ ] **T15: Pydantic schemas** — All schemas from ARCHITECTURE.md section 2.4. `schemas/common.py`, `schemas/fund.py`, `schemas/holdings.py`, `schemas/deviation.py`, `schemas/benchmark.py`, `schemas/pipeline.py`.

- [ ] **T16: Dependencies** — `dependencies.py`. `get_db()` yields AsyncSession, `get_fmp_client()` returns singleton, `require_api_key()` checks X-API-Key header.

- [ ] **T17: API routers** — `routers/health.py` (GET /health, /ready), `routers/funds.py` (GET /api/v1/funds, /api/v1/funds/{ticker}), `routers/holdings.py` (GET /api/v1/funds/{ticker}/holdings), `routers/deviations.py` (GET /api/v1/funds/{ticker}/deviations, /deviations/history), `routers/stocks.py` (GET /api/v1/stocks/{ticker}/holders), `routers/benchmarks.py` (GET /api/v1/benchmarks, /{ticker}/holdings), `routers/pipeline.py` (GET status, POST run, GET runs).

- [ ] **T18: App factory** — `main.py`. `create_app()` with CORS, router includes, APScheduler lifespan, exception handlers for consistent error responses.

### Layer 7: Seed + Docker (depends on Layer 6)

- [ ] **T19: Seed script** — `scripts/seed_funds.py`. Seed 50+ active equity ETFs with benchmark assignments + 4 benchmarks (SPY, QQQ, IWM, VTI). Reads DATABASE_URL from env.

- [ ] **T20: Docker setup** — `backend/Dockerfile` (multi-stage: deps→app→runner, non-root, curl for health), `docker-compose.yml` (backend + postgres + redis, health checks, env vars).

### Layer 8: Tests (parallel with Layers 4-7)

- [ ] **T21: Test fixtures** — `tests/conftest.py`. Async DB session fixture (test DB, auto-rollback), FMP mock (httpx mock transport), test data factories for funds/benchmarks/holdings.

- [ ] **T22: Unit tests** — `test_ticker_normalizer.py` (BRK.B, whitespace, non-equity filter), `test_deviation_service.py` (both sides zero, one side null, leveraged >100%, negative weights, ranking), `test_validation.py` (weight_sum ranges, staleness, ticker format).

- [ ] **T23: Integration tests** — `test_fmp_client.py` (rate limits, retries, parsing), `test_holdings_service.py` (normalize+validate+upsert), `test_bulk_ops.py` (upsert, conflict resolution, idempotent re-run), `test_pipeline_orchestrator.py` (full flow, partial failure, holiday skip).

- [ ] **T24: API tests** — `test_routers/` — test all endpoints with httpx TestClient, verify response shapes match Pydantic schemas, test 404/422 error responses, test pagination, test admin API key requirement on pipeline endpoints.

## Test Plan

| Area                  | Test Type   | Key Cases                                                                                      |
| --------------------- | ----------- | ---------------------------------------------------------------------------------------------- |
| Deviation calculator  | Unit        | Both sides zero, one side null, leveraged weights >100%, negative weights, ranking correctness |
| Ticker normalizer     | Unit        | BRK.B→BRK-B, whitespace, lowercase→uppercase, non-equity filter (USD, CASH), alias resolution  |
| Holdings validator    | Unit        | Weight sum ranges (50%, 85%, 100%, 115%), ticker format regex, date staleness                  |
| Market calendar       | Unit        | Known holidays, weekends, regular trading days                                                 |
| FMP client            | Integration | Rate limit enforcement, retry on 429/5xx, timeout handling, response parsing                   |
| Bulk upserts          | Integration | Insert new, update existing (ON CONFLICT), idempotent re-run                                   |
| Pipeline orchestrator | Integration | Full happy path, partial failure (some funds fail), holiday skip, benchmark failure abort      |
| API endpoints         | Integration | Response shape validation, pagination, filtering, 404/422 errors, admin auth                   |

## Acceptance Criteria

- [ ] `docker-compose up` starts backend + postgres + redis, health endpoint returns 200
- [ ] Alembic migration creates all 8 tables with correct indexes
- [ ] FMP client fetches real holdings for ARKK (with valid API key)
- [ ] Pipeline processes 50+ funds, calculates deviations, stores in DB
- [ ] `GET /api/v1/funds` returns paginated fund list
- [ ] `GET /api/v1/funds/ARKK/deviations` returns ranked deviations vs SPY
- [ ] `GET /api/v1/stocks/TSLA/holders` shows which ETFs hold TSLA
- [ ] Pipeline is idempotent: re-running for same date updates, doesn't duplicate
- [ ] `pytest` passes with >90% coverage on services and utils
- [ ] Pipeline handles market holidays gracefully (skips, doesn't error)
- [ ] Admin endpoints require API key, return 403 without it
