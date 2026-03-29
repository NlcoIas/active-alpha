import { api, type BacktestResult } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Trophy } from "lucide-react";

export const dynamic = "force-dynamic";

function formatPct(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function formatRatio(value: number): string {
  return value.toFixed(2);
}

function describeStrategy(config: BacktestResult["config"]): string {
  const parts = [
    `Top ${config.top_n}`,
    config.direction.replace("_", "-"),
    config.weighting === "equal" ? "EW" : "DW",
    config.rebalance_frequency,
    `vs ${config.benchmark_ticker}`,
  ];
  return parts.join(" / ");
}

export default async function PerformancePage() {
  let strategies: BacktestResult[] = [];
  let error: string | null = null;

  try {
    strategies = await api.getPrecomputedStrategies();
  } catch (err) {
    error =
      err instanceof Error ? err.message : "Failed to load strategies";
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Performance Dashboard
        </h1>
        <p className="mt-1 text-muted-foreground">
          Pre-computed strategy performance comparison
        </p>
      </div>

      {error ? (
        <Card>
          <CardHeader>
            <CardTitle>Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      ) : strategies.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <Trophy className="size-12 text-muted-foreground" />
          <h2 className="text-lg font-semibold">No Pre-computed Strategies</h2>
          <p className="max-w-md text-muted-foreground">
            Run backtests from the Backtest Lab to generate strategies. Pre-computed
            results will appear here.
          </p>
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Strategy</TableHead>
                  <TableHead className="text-right">Return</TableHead>
                  <TableHead className="text-right">Ann. Return</TableHead>
                  <TableHead className="text-right">Sharpe</TableHead>
                  <TableHead className="text-right">Max DD</TableHead>
                  <TableHead className="text-right">Hit Rate</TableHead>
                  <TableHead>Direction</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {strategies.map((strategy, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">
                      {describeStrategy(strategy.config)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        strategy.metrics.cumulative_return >= 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400"
                      }`}
                    >
                      {formatPct(strategy.metrics.cumulative_return)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        strategy.metrics.annualized_return >= 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400"
                      }`}
                    >
                      {formatPct(strategy.metrics.annualized_return)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatRatio(strategy.metrics.sharpe_ratio)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-red-600 dark:text-red-400">
                      {formatPct(strategy.metrics.max_drawdown)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatPct(strategy.metrics.hit_rate)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {strategy.config.direction.replace("_", "-")}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
