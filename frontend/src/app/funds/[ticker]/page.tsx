import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import type { DeviationResponse } from "@/lib/api";
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
import { Separator } from "@/components/ui/separator";
import { ArrowLeft } from "lucide-react";
import { FundDeviationFilter } from "./filter";

export const dynamic = "force-dynamic";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "N/A";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatPct(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
}

type PageProps = {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ direction?: string }>;
};

export default async function FundDetailPage({
  params,
  searchParams,
}: PageProps) {
  const { ticker } = await params;
  const { direction } = await searchParams;
  const upperTicker = ticker.toUpperCase();

  let funds;
  try {
    funds = await api.getFunds();
  } catch {
    notFound();
  }

  const fund = funds.data.find(
    (f) => f.ticker.toUpperCase() === upperTicker
  );

  if (!fund) {
    notFound();
  }

  let deviations: DeviationResponse | null = null;
  let deviationError: string | null = null;

  try {
    deviations = await api.getFundDeviations(upperTicker, {
      direction: direction && direction !== "all" ? direction : undefined,
      limit: 50,
    });
  } catch (err) {
    deviationError =
      err instanceof Error ? err.message : "Failed to load deviations";
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        href="/funds"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to Funds
      </Link>

      <section aria-label="Fund details" className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {fund.ticker}
        </h1>
        <p className="mt-1 text-lg text-muted-foreground">{fund.name}</p>

        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          {fund.provider && (
            <div>
              <span className="text-muted-foreground">Provider: </span>
              <span className="font-medium">{fund.provider}</span>
            </div>
          )}
          {fund.benchmark_ticker && (
            <div>
              <span className="text-muted-foreground">Benchmark: </span>
              <span className="font-medium">{fund.benchmark_ticker}</span>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">Last Update: </span>
            <span className="font-medium">
              {formatDate(fund.last_holdings_date)}
            </span>
          </div>
          {fund.data_quality && (
            <div>
              <span className="text-muted-foreground">Quality: </span>
              <Badge
                variant={
                  fund.data_quality === "good"
                    ? "default"
                    : fund.data_quality === "partial"
                      ? "secondary"
                      : "destructive"
                }
              >
                {fund.data_quality}
              </Badge>
            </div>
          )}
        </div>
      </section>

      <Separator className="mb-8" />

      <section aria-label="Fund deviations">
        <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-xl font-semibold">Top Deviations</h2>
          <FundDeviationFilter
            currentDirection={direction ?? "all"}
            ticker={upperTicker}
          />
        </div>

        {deviationError ? (
          <p className="text-muted-foreground">{deviationError}</p>
        ) : !deviations || deviations.data.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>No Deviations</CardTitle>
              <CardDescription>
                No deviation data found for this fund. The pipeline may not have
                run yet.
              </CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stock</TableHead>
                    <TableHead className="text-right">ETF Wt%</TableHead>
                    <TableHead className="text-right">Bench Wt%</TableHead>
                    <TableHead className="text-right">Deviation</TableHead>
                    <TableHead>Direction</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deviations.data.map((item) => (
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
                        {parseFloat(item.etf_weight_pct).toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {parseFloat(item.benchmark_weight_pct).toFixed(2)}
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
        {deviations && (
          <p className="mt-2 text-sm text-muted-foreground">
            Showing {deviations.data.length} of{" "}
            {deviations.pagination.total_count} deviations
          </p>
        )}
      </section>
    </div>
  );
}
