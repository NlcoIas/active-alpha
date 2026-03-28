# BRIEF.md — Active Alpha

> Active ETF Deviation Tracker & Backtesting Platform
> Replaces: previous alpha site project
> Deploy: alpha.nicolasschaerer.ch via Coolify/Cloudflare Tunnel

---

## Product vision

Every transparent active ETF must publish its exact holdings daily (SEC Rule 6c-11). This creates a massive, free dataset showing exactly what professional fund managers think will outperform — every single day.

**Active Alpha** captures this data, compares it against benchmarks (SPY, QQQ, IWM, etc.), identifies the highest-conviction overweights, backtests whether following those overweights would have generated alpha, and displays everything on an interactive dashboard.

**The core question we answer:** "When active fund managers put significantly more money into a stock than the benchmark holds, does that stock outperform?"

---

## Users

1. **Self-directed investors** — want to know what the smart money is doing today
2. **Quantitative researchers** — want to backtest active deviation strategies
3. **Financial advisors** — want data-driven reasons to recommend active vs. passive
4. **Us** — want to test this as an investment strategy for ourselves

---

## Core features (full product)

### 1. Daily holdings ingestion pipeline

**What it does:**
- Every trading day, pulls complete holdings for ALL transparent active equity ETFs
- Pulls complete holdings for benchmark ETFs (SPY, QQQ, IWM, VTI, etc.)
- Calculates deviation: `ETF_weight(stock) - benchmark_weight(stock)` for every stock in every fund
- Stores daily snapshots in PostgreSQL
- Flags new overweights, removed positions, and significant weight changes

**Scale:**
- Target: 500+ active equity ETFs (all transparent US-listed active equity ETFs)
- Exclude: semi-transparent ETFs (Fidelity ActiveShares, T. Rowe Price Proxy, Blue Tractor), leveraged/inverse, fixed income, commodity
- ~5-10 benchmark indices
- Estimated: 500 funds × 50-200 holdings each = 25,000-100,000 rows per day

**Data sources (priority order):**
1. **ETF provider websites** — direct CSV/JSON downloads (ARK publishes CSV daily, iShares has JSON API, etc.)
2. **Financial Modeling Prep (FMP) API** — ETF holdings endpoint, covers thousands of ETFs, has free tier (250 requests/day) and paid ($29/month for full access)
3. **EODHD API** — ETF fundamentals + holdings, paid ($30/month)
4. **Finnhub API** — ETF holdings endpoint, free tier available
5. **SEC EDGAR** — N-PORT filings (quarterly, 60-day delayed, but useful for historical backfill)
6. **Web scraping** — Playwright-based scraper for ETF provider websites that don't have APIs

**Hybrid approach:** Use free direct sources first (ARK, iShares CSVs), then FMP API for the bulk, then scraping for any gaps. Start with FMP — $29/month gets us the most coverage for the least code.

**Pipeline schedule:**
- Run daily at 7:00 AM ET (after ETFs publish holdings, before market open)
- Retry logic for failed fetches
- Alert on missing data (if a fund that normally reports doesn't)
- Historical backfill: use FMP historical holdings + SEC EDGAR for as far back as possible

### 2. Deviation analysis engine

**What it calculates per fund per day:**

```
For each stock in the ETF:
  etf_weight    = stock's weight in the ETF portfolio (%)
  bench_weight  = stock's weight in the benchmark (%)
  deviation_pct = etf_weight - bench_weight  (percentage points)
  deviation_abs = etf_weight × fund_aum - bench_weight × bench_aum  (dollar amount, if AUM available)
  overweight    = deviation > 0
  underweight   = deviation < 0
```

**Aggregations:**
- Top N overweight stocks per fund (N = 1, 3, 5, 10)
- Consensus overweights: stocks overweighted by the most funds
- Largest absolute deviations
- New entries: stocks that appeared in a fund for the first time today
- Biggest changes: stocks with the largest weight increase/decrease vs. yesterday

### 3. Backtesting engine

**The core hypothesis to test:**
"If you buy the top N overweighted stocks from active ETFs each day/week/month, do you outperform the benchmark?"

**Backtest parameters (all user-configurable):**

| Parameter | Options |
|-----------|---------|
| **Which funds** | All, specific funds, top N by AUM, specific fund families (ARK, JPMorgan, etc.) |
| **Which benchmark** | SPY, QQQ, IWM, VTI, VXUS, custom |
| **Overweight metric** | Percentage deviation, absolute $ deviation, relative deviation (etf_weight / bench_weight) |
| **Number of stocks** | Top 1, 2, 3, 5, 10, 20 overweighted |
| **Rebalance frequency** | Daily, weekly, monthly |
| **Holding period** | 1 day, 1 week, 1 month, 3 months, 6 months, 1 year |
| **Minimum deviation threshold** | >0%, >1%, >2%, >5% |
| **Weighting scheme** | Equal weight, deviation-weighted, market-cap weighted |
| **Lookback period** | 1Y, 2Y, 3Y, 5Y, all available history |
| **Long/short** | Long only (overweights), long-short (overweights + underweights), short only (underweights) |

**Output metrics:**
- Cumulative return vs. benchmark
- Annualized return
- Sharpe ratio
- Sortino ratio
- Maximum drawdown
- Hit rate (% of picks that outperformed)
- Win/loss ratio
- Turnover rate
- Transaction cost impact (configurable bps)
- Monthly returns heatmap
- Rolling Sharpe ratio

**Pre-computed strategies:**
Run the most common backtests nightly and cache results so users get instant results. Custom combinations compute on-demand.

### 4. Dashboard & visualization

**Pages:**

#### Home / Today's signals
- Top overweighted stocks across all funds today
- Consensus picks (overweighted by 5+ funds)
- Biggest weight changes vs. yesterday
- "New conviction" — stocks that just entered top overweight positions
- Quick stats: how many funds tracked, last update time, total AUM tracked

#### Fund explorer
- Browse all tracked active ETFs
- For each fund: current top overweights, historical accuracy, AUM, expense ratio
- Compare two funds side-by-side
- Fund family grouping (ARK, JPMorgan, Dimensional, etc.)

#### Stock lookup
- Search any stock → see which funds overweight it and by how much
- Historical chart: overweight trend over time
- Forward performance after overweight events

#### Backtest lab
- Full interactive backtest configuration (all parameters above)
- Real-time chart updates as you adjust parameters
- Export results as CSV
- Save and name custom strategies
- Share backtest configs via URL

#### Performance dashboard
- Pre-computed strategy performance (updated nightly)
- Leaderboard: which funds have the best historical overweight accuracy?
- Time-series: cumulative performance of top strategies vs. benchmarks
- Drawdown analysis

#### Alerts (future)
- Set alerts for: specific stock overweighted by N+ funds, specific fund changes top holdings, strategy performance threshold crossed

### 5. API (future monetization)

REST API for programmatic access:
- `/api/v1/holdings/{fund}/{date}` — daily holdings
- `/api/v1/deviation/{fund}/{benchmark}/{date}` — deviations
- `/api/v1/consensus/{benchmark}/{date}` — consensus overweights
- `/api/v1/backtest` — run custom backtest
- Rate limited, API key required
- Free tier: 100 requests/day
- Paid tier: unlimited ($29/month)

---

## Tech stack

### Backend (FastAPI)
```
Framework:     FastAPI + Pydantic v2
Database:      PostgreSQL (via async SQLAlchemy + Alembic migrations)
Cache:         Redis (backtest result cache, rate limiting)
Scheduler:     APScheduler (daily pipeline) or cron
Data:          Pandas + NumPy for computation
HTTP client:   httpx (async, for API calls)
Scraping:      Playwright (for ETF websites without APIs)
Task queue:    Celery + Redis (for async backtest computation)
```

### Frontend (Next.js + React)
```
Framework:     Next.js 15+ (App Router)
UI:            shadcn/ui + Tailwind CSS
Charts:        Recharts or Lightweight Charts (TradingView)
Tables:        TanStack Table (sortable, filterable, paginated)
State:         Zustand
Forms:         React Hook Form + Zod validation
Auth:          NextAuth.js (if we add user accounts / saved strategies)
```

### Infrastructure
```
Deploy:        Coolify on Proxmox VM
Tunnel:        Cloudflare Tunnel → alpha.nicolasschaerer.ch
Database:      PostgreSQL (Docker container via Coolify)
Cache:         Redis (Docker container via Coolify)
Monitoring:    Health check endpoint + Coolify alerts
Backups:       Daily PostgreSQL dumps to local storage
```

### Data flow
```
[ETF Provider APIs/Websites]
        ↓ (daily 7am ET)
[Ingestion Pipeline - FastAPI scheduler]
        ↓
[PostgreSQL - daily snapshots]
        ↓
[Deviation Calculator]
        ↓
[PostgreSQL - deviation tables]
        ↓                          ↓
[Nightly Backtest Runner]    [On-demand Backtest API]
        ↓                          ↓
[Redis Cache]                [Redis Cache]
        ↓                          ↓
[Next.js Frontend - SSR/API Routes]
        ↓
[User's Browser]
```

---

## Data model (core entities)

### funds
```
id              UUID PK
ticker          VARCHAR(10) UNIQUE NOT NULL     -- e.g., "ARKK"
name            VARCHAR(255) NOT NULL           -- e.g., "ARK Innovation ETF"
provider        VARCHAR(100)                    -- e.g., "ARK Invest"
type            ENUM(transparent, semi_transparent, passive)
asset_class     ENUM(equity, fixed_income, commodity, multi_asset)
benchmark_id    UUID FK → benchmarks.id         -- primary benchmark
aum             DECIMAL                         -- latest AUM
expense_ratio   DECIMAL
inception_date  DATE
data_source     VARCHAR(50)                     -- e.g., "fmp_api", "ark_csv", "scrape"
is_active       BOOLEAN DEFAULT true
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### benchmarks
```
id              UUID PK
ticker          VARCHAR(10) UNIQUE NOT NULL     -- e.g., "SPY"
name            VARCHAR(255) NOT NULL
index_name      VARCHAR(255)                    -- e.g., "S&P 500"
created_at      TIMESTAMP
```

### holdings_snapshots
```
id              UUID PK
fund_id         UUID FK → funds.id NOT NULL
date            DATE NOT NULL
stock_ticker    VARCHAR(10) NOT NULL
stock_name      VARCHAR(255)
shares          DECIMAL
market_value    DECIMAL
weight_pct      DECIMAL(8,5) NOT NULL           -- e.g., 5.23400
created_at      TIMESTAMP

UNIQUE(fund_id, date, stock_ticker)
INDEX(fund_id, date)
INDEX(stock_ticker, date)
```

### benchmark_holdings
```
id              UUID PK
benchmark_id    UUID FK → benchmarks.id NOT NULL
date            DATE NOT NULL
stock_ticker    VARCHAR(10) NOT NULL
weight_pct      DECIMAL(8,5) NOT NULL
created_at      TIMESTAMP

UNIQUE(benchmark_id, date, stock_ticker)
INDEX(benchmark_id, date)
```

### deviations
```
id              UUID PK
fund_id         UUID FK → funds.id NOT NULL
benchmark_id    UUID FK → benchmarks.id NOT NULL
date            DATE NOT NULL
stock_ticker    VARCHAR(10) NOT NULL
fund_weight     DECIMAL(8,5)
benchmark_weight DECIMAL(8,5)
deviation_pct   DECIMAL(8,5)                    -- fund_weight - benchmark_weight
deviation_rank  INTEGER                         -- rank within fund for that day (1 = most overweight)
created_at      TIMESTAMP

UNIQUE(fund_id, benchmark_id, date, stock_ticker)
INDEX(fund_id, date, deviation_rank)
INDEX(stock_ticker, date)
```

### stock_prices
```
id              UUID PK
ticker          VARCHAR(10) NOT NULL
date            DATE NOT NULL
open            DECIMAL
high            DECIMAL
low             DECIMAL
close           DECIMAL NOT NULL
adj_close       DECIMAL NOT NULL
volume          BIGINT
created_at      TIMESTAMP

UNIQUE(ticker, date)
INDEX(ticker, date)
```

### backtest_results (cache)
```
id              UUID PK
config_hash     VARCHAR(64) UNIQUE NOT NULL     -- SHA256 of params
config_json     JSONB NOT NULL                  -- full parameter set
result_json     JSONB NOT NULL                  -- metrics + time series
computed_at     TIMESTAMP
expires_at      TIMESTAMP                       -- cache TTL
```

---

## Build phases

### Phase 1: Data pipeline + core backend (weeks 1-4)
- [ ] Database schema + migrations (Alembic)
- [ ] Fund registry: seed with top 50 active equity ETFs + 5 benchmarks
- [ ] FMP API integration: fetch daily holdings
- [ ] ARK CSV direct download integration
- [ ] Benchmark holdings fetcher (SPY, QQQ, IWM, VTI)
- [ ] Stock price fetcher (daily close, for backtesting)
- [ ] Deviation calculator: compute and store daily deviations
- [ ] Scheduled pipeline: daily run at 7am ET
- [ ] Historical backfill: fill as much history as FMP provides
- [ ] Health check + logging + error alerts
- [ ] API endpoints: /funds, /holdings/{fund}/{date}, /deviations/{fund}/{benchmark}/{date}
- [ ] Tests: pipeline tests, deviation calculation tests, API tests

### Phase 2: Backtesting engine (weeks 5-7)
- [ ] Backtest core: given parameters, simulate the strategy and compute returns
- [ ] All configurable parameters from spec
- [ ] Metrics calculation: Sharpe, Sortino, max drawdown, hit rate, etc.
- [ ] Pre-computed nightly strategies (top 5 most common configs)
- [ ] On-demand backtest API endpoint with Redis caching
- [ ] Celery async task for long-running backtests
- [ ] Tests: backtest accuracy tests (compare against manual calculations)

### Phase 3: Frontend — dashboard (weeks 8-11)
- [ ] Layout: sidebar nav, responsive, dark/light mode
- [ ] Home page: today's signals, consensus picks, biggest changes
- [ ] Fund explorer: browse, filter, fund detail pages
- [ ] Stock lookup: search + overweight history chart
- [ ] Data tables: sortable, filterable, paginated (TanStack Table)
- [ ] Charts: deviation trends, fund performance (Recharts or TradingView)
- [ ] Screenshot testing at all viewports

### Phase 4: Frontend — backtest lab (weeks 12-14)
- [ ] Backtest configuration form (all parameters)
- [ ] Real-time chart updates as params change
- [ ] Results display: metrics cards + equity curve + drawdown chart + monthly heatmap
- [ ] Strategy comparison: overlay multiple strategies
- [ ] CSV export
- [ ] URL-shareable configs
- [ ] Performance dashboard with leaderboard

### Phase 5: Scale + polish (weeks 15-17)
- [ ] Expand to 500+ ETFs (full FMP coverage)
- [ ] Additional data sources for gaps (EODHD, scraping)
- [ ] Performance optimization: database indexes, query optimization, caching
- [ ] SEO: static pages for top funds, meta tags, OG images
- [ ] Mobile responsive polish
- [ ] Error handling, loading states, empty states everywhere
- [ ] Security audit
- [ ] Deploy to alpha.nicolasschaerer.ch

### Phase 6: Future / monetization
- [ ] Public API with rate limiting + API keys
- [ ] Email alerts for overweight signals
- [ ] User accounts + saved strategies
- [ ] Premium tier (more backtest history, real-time updates, API access)
- [ ] Newsletter: weekly digest of top signals

---

## Key design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | PostgreSQL | Time-series queries, JSONB for flexible backtest configs, proven at scale |
| Backend | FastAPI | Async, fast, Pydantic validation, you know it well |
| Frontend | Next.js | SSR for SEO, App Router for layouts, shadcn for rapid UI |
| Charts | TradingView Lightweight Charts | Finance-native, performant with large datasets, professional look |
| Primary data source | FMP API | Best coverage/price ratio, 1000+ ETFs, historical data |
| Backtest compute | Pandas + NumPy | Fast vectorized operations, well-tested financial math |
| Task queue | Celery + Redis | Async long-running backtests without blocking API |
| Cache | Redis | Fast backtest result cache, configurable TTL |
| Deploy | Coolify + Cloudflare | Existing infrastructure, zero additional cost |

---

## Non-goals (explicitly out of scope)

- Real-time intraday data (daily EOD is sufficient)
- Trading execution / brokerage integration
- Portfolio tracking (this is analysis only)
- Options / derivatives analysis
- International ETFs (US-listed only for v1)
- Mobile app (responsive web is sufficient)

---

## Success metrics

| Metric | Target |
|--------|--------|
| ETFs tracked | 500+ transparent active equity ETFs |
| Data freshness | Updated by 8am ET every trading day |
| Historical depth | 2+ years of daily deviation data |
| Backtest speed | <5 seconds for common configs (cached), <30 seconds for custom |
| Page load | <2 seconds for dashboard pages |
| Uptime | 99%+ |
