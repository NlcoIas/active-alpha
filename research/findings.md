# Research Findings — Active Alpha

Date: 2026-03-29

## Current State Assessment

### Backend (COMPLETE — Phase 1 of BRIEF)
- **Models**: Fund, Benchmark, BenchmarkHolding, Deviation, HoldingsSnapshot, PipelineRun, StockPrice, TickerMapping
- **Services**: DeviationService (FULL OUTER JOIN calculation, cross-fund stock holders), HoldingsService, BenchmarkService, FundService, PipelineOrchestrator (3-stage: holdings → benchmarks → deviations)
- **Clients**: Multi-source aggregator (FMP, ARK CSV, iShares, Invesco, SSGA) — free-first strategy
- **Routers**: /api/v1/funds, holdings, deviations, benchmarks, pipeline, health
- **Scheduler**: APScheduler daily at 7am ET
- **Docker**: Multi-stage Dockerfile, docker-compose (backend + postgres + redis)
- **Migrations**: Alembic with initial schema
- **Tests**: market_calendar, ticker_normalizer, validation, fmp_client

### Frontend (NOT STARTED)
- Empty `frontend/` directory
- No Next.js project scaffolded

### Missing from BRIEF
1. **Stock price fetcher** — StockPrice model exists but no fetcher service
2. **Backtesting engine** — core BRIEF Phase 2, not implemented
3. **Backtest API endpoints** — no router
4. **Frontend dashboard** — BRIEF Phase 3, not started
5. **Backtest lab UI** — BRIEF Phase 4, not started

## Feature Implementation Approaches

### 1. Backtesting Engine
**Approach**: Synchronous NumPy/Pandas computation, Redis-cached results
- No Celery needed for MVP — backtests complete in <30s for typical configs
- Cache by SHA256 hash of parameter config
- Pre-compute top 5 strategies nightly via scheduler

**Parameters**: funds, benchmark, overweight metric, N stocks, rebalance freq, holding period, min deviation threshold, weighting scheme, lookback period, long/short

**Output metrics**: cumulative return, annualized return, Sharpe, Sortino, max drawdown, hit rate, win/loss ratio, turnover, transaction cost impact, monthly returns, rolling Sharpe

**Stock price data**: Use yfinance for historical prices (free, sufficient for daily backtesting). Store in stock_prices table.

### 2. Frontend Architecture
**Approach**: Next.js 15 App Router with route handlers proxying to FastAPI backend
- API calls via Next.js route handlers (avoids CORS, SSR-friendly)
- Client-side charts with TradingView Lightweight Charts
- TanStack Table for sortable/filterable data tables
- Zustand for client state (backtest params, filters)
- shadcn/ui for components, dark/light mode

**Pages**:
1. Home — today's signals, consensus picks, biggest changes
2. Fund Explorer — browse/filter funds, fund detail pages
3. Stock Lookup — search stock, see which ETFs overweight it
4. Backtest Lab — parameter form, equity curve, metrics
5. Performance — pre-computed strategy leaderboard

### 3. Production Architecture
**Approach**: nginx reverse proxy in docker-compose
- nginx:80 → /api/* to backend:8000, /* to frontend:3000
- Single Coolify app (docker-compose), single domain
- Cloudflare Tunnel handles SSL

### 4. Acceptance Criteria

| Feature | Acceptance Criteria |
|---------|-------------------|
| Home page | Shows top 10 overweighted stocks, consensus picks (5+ funds), last update time |
| Fund explorer | Lists all active funds, sortable by ticker/name/provider, click to detail |
| Fund detail | Top overweights table, deviation chart over time, fund metadata |
| Stock lookup | Search by ticker, shows all ETFs holding it with deviation data |
| Backtest lab | All parameters configurable, chart updates on submit, metrics displayed |
| Backtest results | Equity curve, drawdown chart, monthly heatmap, key metrics cards |
| Performance | Leaderboard of pre-computed strategies sorted by Sharpe ratio |
| Responsive | Mobile-first, readable on 375px, tables scroll horizontally |
| Dark mode | Toggle in header, persists via cookie |
| API health | /health returns 200, /ready checks DB connection |
