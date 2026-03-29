import Link from "next/link";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/api";
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
import { Badge } from "@/components/ui/badge";
import { BarChart3, TrendingUp, Clock } from "lucide-react";

export const dynamic = "force-dynamic";

function formatPct(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "N/A";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default async function HomePage() {
  let data: DashboardSummary | null = null;
  let error: string | null = null;

  try {
    data = await api.getDashboardSummary();
  } catch (err) {
    error =
      err instanceof Error ? err.message : "Failed to load dashboard data";
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
          <BarChart3 className="size-12 text-muted-foreground" />
          <h1 className="text-2xl font-semibold">Active Alpha</h1>
          <p className="max-w-md text-muted-foreground">
            {error ||
              "No data yet — run the pipeline to populate the database."}
          </p>
        </div>
      </div>
    );
  }

  const { stats, top_overweights, consensus_picks } = data;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Today&apos;s Signals
        </h1>
        <p className="mt-1 text-muted-foreground">
          Active ETF deviation analysis
        </p>
      </div>

      <section aria-label="Summary statistics" className="mb-10">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Funds Tracked
              </CardTitle>
              <BarChart3 className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{stats.funds_with_data}</p>
              <p className="text-xs text-muted-foreground">
                of {stats.total_funds} registered
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Deviations
              </CardTitle>
              <TrendingUp className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {stats.total_deviations.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">
                active position deviations
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Last Update
              </CardTitle>
              <Clock className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {formatDate(stats.latest_date)}
              </p>
              <p className="text-xs text-muted-foreground">
                most recent snapshot
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      <section aria-label="Top overweights" className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">Top Overweights Today</h2>
        {top_overweights.length === 0 ? (
          <p className="text-muted-foreground">
            No overweight positions found.
          </p>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rank</TableHead>
                    <TableHead>Stock</TableHead>
                    <TableHead>Fund</TableHead>
                    <TableHead className="text-right">ETF Wt%</TableHead>
                    <TableHead className="text-right">Bench Wt%</TableHead>
                    <TableHead className="text-right">Deviation</TableHead>
                    <TableHead>Direction</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {top_overweights.slice(0, 20).map((item, idx) => (
                    <TableRow key={`${item.ticker}-${item.fund_ticker}-${idx}`}>
                      <TableCell className="font-medium">
                        {item.deviation_rank}
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/stocks/${item.ticker}`}
                          className="font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {item.ticker}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/funds/${item.fund_ticker}`}
                          className="text-primary underline-offset-4 hover:underline"
                        >
                          {item.fund_ticker}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {item.etf_weight_pct?.toFixed(2) ?? "N/A"}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {item.benchmark_weight_pct?.toFixed(2) ?? "N/A"}
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium">
                        {formatPct(item.deviation_pct)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            item.direction === "overweight"
                              ? "default"
                              : "secondary"
                          }
                        >
                          {item.direction}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </section>

      <section aria-label="Consensus picks">
        <h2 className="mb-4 text-xl font-semibold">Consensus Picks</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Stocks overweighted by 3 or more active ETFs
        </p>
        {consensus_picks.length === 0 ? (
          <p className="text-muted-foreground">No consensus picks found.</p>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stock</TableHead>
                    <TableHead className="text-right">Fund Count</TableHead>
                    <TableHead className="text-right">Avg Deviation</TableHead>
                    <TableHead className="text-right">Max Deviation</TableHead>
                    <TableHead>Funds</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {consensus_picks.map((item) => (
                    <TableRow key={item.ticker}>
                      <TableCell>
                        <Link
                          href={`/stocks/${item.ticker}`}
                          className="font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {item.ticker}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {item.fund_count}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatPct(item.avg_deviation_pct)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatPct(item.max_deviation_pct)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {item.funds.map((fund) => (
                            <Link key={fund} href={`/funds/${fund}`}>
                              <Badge variant="outline">{fund}</Badge>
                            </Link>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
