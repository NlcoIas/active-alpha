# BUILD-PLAN — Active Alpha

Date: 2026-03-29

## Architecture

```
[Browser] → [Cloudflare Tunnel] → [nginx:80]
                                    ├── /api/*     → [backend:8000] (FastAPI)
                                    ├── /docs      → [backend:8000]
                                    ├── /health    → [backend:8000]
                                    ├── /ready     → [backend:8000]
                                    └── /*         → [frontend:3000] (Next.js)
```

All services run in one docker-compose stack deployed as a single Coolify app.

---

## Task List

### Backend Tasks (backtesting engine)

#### B1: Stock Price Fetcher Service
- Add `app/services/price_service.py` — fetch daily OHLCV from yfinance
- Bulk upsert into stock_prices table
- Add router endpoint: POST /api/v1/prices/fetch (admin-protected)
- **Acceptance**: Can fetch and store 1yr of daily prices for any ticker

#### B2: Backtest Engine Core
- Add `app/services/backtest_engine.py`
- Input: BacktestConfig (funds, benchmark, metric, N stocks, rebalance freq, holding period, min deviation, weighting, lookback, long/short, transaction costs)
- Process: For each rebalance date, get top N overweight stocks, simulate portfolio, compute returns
- Output: BacktestResult (equity curve, metrics, monthly returns)
- **Acceptance**: Given historical deviations and prices, produces correct cumulative returns matching manual calculation

#### B3: Backtest Metrics Calculator
- Cumulative return, annualized return, Sharpe ratio, Sortino ratio, max drawdown, hit rate, win/loss ratio, turnover, transaction cost impact, monthly returns heatmap data, rolling Sharpe
- **Acceptance**: Sharpe ratio matches manual calculation for a known return series

#### B4: Backtest Caching (Redis)
- SHA256 hash of config params → cache key
- Store result as JSON in Redis with 24h TTL
- Check cache before computing
- **Acceptance**: Second call with same params returns cached result in <100ms

#### B5: Backtest API Endpoints
- Add `app/routers/backtests.py`
- POST /api/v1/backtests/run — run backtest with config
- GET /api/v1/backtests/precomputed — list pre-computed strategies
- GET /api/v1/backtests/precomputed/{strategy_id} — get specific pre-computed result
- **Acceptance**: POST returns backtest results with all metrics

#### B6: Consensus Overweights Endpoint
- GET /api/v1/deviations/consensus — stocks overweighted by N+ funds
- Query param: min_funds (default 3), date
- **Acceptance**: Returns stocks held by 3+ funds with their average deviation

#### B7: Top Signals / Dashboard Summary Endpoint
- GET /api/v1/dashboard/summary — aggregated signals for home page
- Returns: top overweights, consensus picks, biggest weight changes, stats
- **Acceptance**: Returns complete summary object with all required fields

### Frontend Tasks

#### F1: Scaffold Next.js Project
- `npx create-next-app@latest` with TypeScript, Tailwind, App Router
- Install: shadcn/ui, TanStack Table, Lightweight Charts, Zustand, React Hook Form, Zod, next-themes
- Configure next.config.ts: standalone output, security headers (no HSTS)
- Add Dockerfile for Next.js
- **Acceptance**: `npm run build` passes

#### F2: Layout & Navigation
- Root layout with ThemeProvider, fonts, metadata
- Header: logo, nav links (Home, Funds, Stocks, Backtest, Performance), dark mode toggle
- Footer: project name, links
- Sidebar nav on desktop, hamburger on mobile
- Skip-to-content link
- **Acceptance**: Navigation works on all viewports, dark mode toggles

#### F3: API Client Layer
- Next.js route handlers proxying to FastAPI backend
- `src/lib/api.ts` — typed fetch wrapper for all API calls
- Error handling with typed responses
- **Acceptance**: All backend endpoints accessible from frontend components

#### F4: Home Page — Today's Signals
- Top overweighted stocks across all funds (table)
- Consensus picks (stocks overweighted by 5+ funds)
- Quick stats cards: funds tracked, last update, total deviations
- **Acceptance**: Page loads with real data from API, responsive on mobile

#### F5: Fund Explorer Page
- Filterable/sortable table of all tracked funds (TanStack Table)
- Columns: ticker, name, provider, benchmark, last update, top overweight
- Click row → fund detail page
- **Acceptance**: Table sorts, filters, paginates correctly

#### F6: Fund Detail Page
- Fund metadata header (name, ticker, provider, benchmark, AUM, expense ratio)
- Top overweights table (sortable by deviation)
- Deviation history chart for selected stock (Lightweight Charts)
- **Acceptance**: Shows real deviation data, chart renders time series

#### F7: Stock Lookup Page
- Search input with autocomplete
- Results: which ETFs hold this stock, with deviation data
- Deviation trend chart over time
- **Acceptance**: Search returns results, chart renders

#### F8: Backtest Lab Page
- Full parameter form (all params from BRIEF)
- Submit triggers backtest API call
- Results: equity curve chart, drawdown chart, monthly heatmap
- Metrics cards: return, Sharpe, max drawdown, hit rate
- Loading state during computation
- **Acceptance**: Form submits, chart renders with backtest results

#### F9: Performance Dashboard Page
- Pre-computed strategy leaderboard table
- Columns: strategy name, return, Sharpe, max drawdown, hit rate
- Click to expand with equity curve
- **Acceptance**: Table loads pre-computed strategies, sortable

#### F10: Responsive & Mobile Polish
- All pages work at 375px
- Tables scroll horizontally on mobile
- Touch-friendly controls (44px+ targets)
- Charts resize properly
- **Acceptance**: No overflow issues at 375px

### Infrastructure Tasks

#### I1: nginx Reverse Proxy Config
- nginx.conf routing /api/* to backend, /* to frontend
- Add nginx service to docker-compose.yml
- Expose port 80 (Coolify/Traefik will proxy to it)
- **Acceptance**: Requests route correctly to backend and frontend

#### I2: Frontend Dockerfile
- Multi-stage: deps → builder → runner
- standalone output, copy public + static
- Non-root user, curl healthcheck
- **Acceptance**: `docker build` succeeds, container starts

#### I3: Update docker-compose.yml
- Add frontend and nginx services
- nginx depends on frontend and backend
- Update port mapping
- **Acceptance**: `docker-compose up` starts all services

#### I4: Update Deploy Script
- Update Coolify domain routing to nginx:80
- Update env vars for frontend (NEXT_PUBLIC_API_URL if needed)
- **Acceptance**: Deploy script configures Coolify correctly

---

## Dependency Order

```
B1 (prices) ──→ B2 (backtest engine) ──→ B3 (metrics) ──→ B4 (cache) ──→ B5 (API)
                                                                            ↓
F1 (scaffold) ──→ F2 (layout) ──→ F3 (API client) ──→ F4-F9 (pages) ──→ F10 (polish)
                                                                            ↓
I1 (nginx) + I2 (frontend Dockerfile) ──→ I3 (docker-compose) ──→ I4 (deploy)
```

Backend and frontend can be built in parallel (F3 needs API contracts, not running backend).
