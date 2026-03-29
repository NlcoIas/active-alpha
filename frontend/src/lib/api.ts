const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type ApiOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {} } = options;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(error.error || `API error: ${res.status}`);
  }

  return res.json();
}

// Dashboard summary
export type DashboardSummary = {
  top_overweights: DeviationItem[];
  consensus_picks: ConsensusItem[];
  stats: {
    total_funds: number;
    funds_with_data: number;
    latest_date: string | null;
    total_deviations: number;
  };
};

export type DeviationItem = {
  ticker: string;
  fund_ticker: string;
  benchmark_ticker: string | null;
  snapshot_date: string;
  etf_weight_pct: number | null;
  benchmark_weight_pct: number | null;
  deviation_pct: number;
  abs_deviation_pct: number;
  deviation_rank: number;
  direction: string;
};

export type ConsensusItem = {
  ticker: string;
  fund_count: number;
  avg_deviation_pct: number;
  max_deviation_pct: number;
  funds: string[];
};

export type Fund = {
  id: string;
  ticker: string;
  name: string;
  provider: string | null;
  fund_type: string;
  asset_class: string;
  benchmark_ticker: string | null;
  aum: number | null;
  expense_ratio: number | null;
  is_active: boolean;
  last_holdings_date: string | null;
  data_quality: string | null;
};

export type FundListResponse = {
  data: Fund[];
  total_count: number;
};

export type DeviationRecord = {
  ticker: string;
  etf_weight_pct: string;
  benchmark_weight_pct: string;
  deviation_pct: string;
  abs_deviation_pct: string;
  direction: string;
};

export type DeviationResponse = {
  fund_ticker: string;
  benchmark_ticker: string;
  snapshot_date: string;
  data: DeviationRecord[];
  pagination: {
    next_cursor: string | null;
    has_more: boolean;
    total_count: number;
  };
};

export type StockHolder = {
  fund_ticker: string;
  fund_name: string;
  etf_weight_pct: string;
  benchmark_weight_pct: string;
  deviation_pct: string;
  direction: string;
};

export type StockHoldersResponse = {
  stock_ticker: string;
  snapshot_date: string;
  data: StockHolder[];
  pagination: {
    next_cursor: string | null;
    has_more: boolean;
    total_count: number;
  };
};

export type BacktestConfig = {
  benchmark_ticker: string;
  fund_tickers?: string[];
  top_n: number;
  rebalance_frequency: "daily" | "weekly" | "monthly";
  holding_period_days: number;
  min_deviation_pct: number;
  weighting: "equal" | "deviation_weighted";
  lookback_years: number;
  direction: "long" | "short" | "long_short";
  transaction_cost_bps: number;
};

export type BacktestResult = {
  config: BacktestConfig;
  metrics: {
    cumulative_return: number;
    annualized_return: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown: number;
    hit_rate: number;
    win_loss_ratio: number;
    turnover: number;
    total_trades: number;
  };
  equity_curve: { date: string; value: number; benchmark: number }[];
  monthly_returns: { year: number; month: number; return_pct: number }[];
  benchmark_metrics: {
    cumulative_return: number;
    annualized_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
  };
};

export type HealthResponse = {
  status: string;
  version: string;
  environment: string;
};

// API functions
export const api = {
  health: () => apiFetch<HealthResponse>("/api/v1/health"),

  getDashboardSummary: (date?: string) =>
    apiFetch<DashboardSummary>(
      `/api/v1/dashboard/summary${date ? `?date=${date}` : ""}`
    ),

  getFunds: (params?: { provider?: string; active_only?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.provider) search.set("provider", params.provider);
    if (params?.active_only !== undefined)
      search.set("active_only", String(params.active_only));
    const qs = search.toString();
    return apiFetch<FundListResponse>(`/api/v1/funds${qs ? `?${qs}` : ""}`);
  },

  getFundDeviations: (
    ticker: string,
    params?: { date?: string; direction?: string; limit?: number }
  ) => {
    const search = new URLSearchParams();
    if (params?.date) search.set("date", params.date);
    if (params?.direction) search.set("direction", params.direction);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return apiFetch<DeviationResponse>(
      `/api/v1/funds/${ticker}/deviations${qs ? `?${qs}` : ""}`
    );
  },

  getStockHolders: (ticker: string, params?: { date?: string }) => {
    const search = new URLSearchParams();
    if (params?.date) search.set("date", params.date);
    const qs = search.toString();
    return apiFetch<StockHoldersResponse>(
      `/api/v1/stocks/${ticker}/holders${qs ? `?${qs}` : ""}`
    );
  },

  getConsensus: (params?: { min_funds?: number; date?: string }) => {
    const search = new URLSearchParams();
    if (params?.min_funds) search.set("min_funds", String(params.min_funds));
    if (params?.date) search.set("date", params.date);
    const qs = search.toString();
    return apiFetch<{ data: ConsensusItem[]; snapshot_date: string }>(
      `/api/v1/deviations/consensus${qs ? `?${qs}` : ""}`
    );
  },

  runBacktest: (config: BacktestConfig) =>
    apiFetch<BacktestResult>("/api/v1/backtests/run", {
      method: "POST",
      body: config,
    }),

  getPrecomputedStrategies: () =>
    apiFetch<{ strategies: BacktestResult[] }>(
      "/api/v1/backtests/precomputed"
    ),
};
