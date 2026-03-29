"use client";

import { type BacktestResult } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EquityCurveChart } from "./equity-chart";

function formatPct(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function formatRatio(value: number): string {
  return value.toFixed(2);
}

const MONTH_NAMES = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

type BacktestResultsProps = {
  result: BacktestResult;
};

export function BacktestResults({ result }: BacktestResultsProps) {
  const { metrics, benchmark_metrics, equity_curve, monthly_returns } = result;

  const metricCards = [
    {
      label: "Cumulative Return",
      value: formatPct(metrics.cumulative_return),
      benchmark: formatPct(benchmark_metrics.cumulative_return),
    },
    {
      label: "Annualized Return",
      value: formatPct(metrics.annualized_return),
      benchmark: formatPct(benchmark_metrics.annualized_return),
    },
    {
      label: "Sharpe Ratio",
      value: formatRatio(metrics.sharpe_ratio),
      benchmark: formatRatio(benchmark_metrics.sharpe_ratio),
    },
    {
      label: "Max Drawdown",
      value: formatPct(metrics.max_drawdown),
      benchmark: formatPct(benchmark_metrics.max_drawdown),
    },
    {
      label: "Hit Rate",
      value: formatPct(metrics.hit_rate),
      benchmark: null,
    },
    {
      label: "Win/Loss Ratio",
      value: formatRatio(metrics.win_loss_ratio),
      benchmark: null,
    },
    {
      label: "Sortino Ratio",
      value: formatRatio(metrics.sortino_ratio),
      benchmark: null,
    },
    {
      label: "Total Trades",
      value: metrics.total_trades.toLocaleString(),
      benchmark: null,
    },
    {
      label: "Turnover",
      value: formatPct(metrics.turnover),
      benchmark: null,
    },
  ];

  // Group monthly returns by year
  const yearMap = new Map<number, Map<number, number>>();
  for (const entry of monthly_returns) {
    if (!yearMap.has(entry.year)) {
      yearMap.set(entry.year, new Map());
    }
    yearMap.get(entry.year)?.set(entry.month, entry.return_pct);
  }
  const years = Array.from(yearMap.keys()).sort();

  return (
    <div className="space-y-6">
      <section aria-label="Performance metrics">
        <h2 className="mb-4 text-xl font-semibold">Performance Metrics</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {metricCards.map((card) => (
            <Card key={card.label} size="sm">
              <CardContent className="pt-3">
                <p className="text-xs text-muted-foreground">{card.label}</p>
                <p className="text-lg font-bold">{card.value}</p>
                {card.benchmark !== null && (
                  <p className="text-xs text-muted-foreground">
                    Benchmark: {card.benchmark}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {equity_curve.length > 0 && (
        <section aria-label="Equity curve">
          <h2 className="mb-4 text-xl font-semibold">Equity Curve</h2>
          <Card>
            <CardContent className="pt-4">
              <EquityCurveChart data={equity_curve} />
            </CardContent>
          </Card>
        </section>
      )}

      {years.length > 0 && (
        <section aria-label="Monthly returns">
          <h2 className="mb-4 text-xl font-semibold">Monthly Returns</h2>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Year</TableHead>
                    {MONTH_NAMES.map((m) => (
                      <TableHead key={m} className="text-center">
                        {m}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {years.map((year) => (
                    <TableRow key={year}>
                      <TableCell className="font-medium">{year}</TableCell>
                      {Array.from({ length: 12 }).map((_, monthIdx) => {
                        const value = yearMap
                          .get(year)
                          ?.get(monthIdx + 1);
                        if (value === undefined) {
                          return (
                            <TableCell
                              key={monthIdx}
                              className="text-center text-muted-foreground"
                            >
                              -
                            </TableCell>
                          );
                        }
                        const pct = value * 100;
                        return (
                          <TableCell
                            key={monthIdx}
                            className={`text-center font-mono text-xs ${
                              pct > 0
                                ? "text-green-600 dark:text-green-400"
                                : pct < 0
                                  ? "text-red-600 dark:text-red-400"
                                  : ""
                            }`}
                          >
                            {pct.toFixed(1)}%
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
