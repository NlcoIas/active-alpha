import Link from "next/link";
import { api } from "@/lib/api";
import type { StockHoldersResponse } from "@/lib/api";
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
import { ArrowLeft } from "lucide-react";

export const dynamic = "force-dynamic";

function formatPct(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
}

type PageProps = {
  params: Promise<{ ticker: string }>;
};

export default async function StockDetailPage({ params }: PageProps) {
  const { ticker } = await params;
  const upperTicker = ticker.toUpperCase();

  let data: StockHoldersResponse | null = null;
  let error: string | null = null;

  try {
    data = await api.getStockHolders(upperTicker);
  } catch (err) {
    error =
      err instanceof Error ? err.message : "Failed to load stock data";
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        href="/stocks"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to Stocks
      </Link>

      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {upperTicker}
        </h1>
        <p className="mt-1 text-muted-foreground">
          ETF holdings and deviation analysis
        </p>
        {data?.snapshot_date && (
          <p className="mt-1 text-sm text-muted-foreground">
            Snapshot: {data.snapshot_date}
          </p>
        )}
      </div>

      {error ? (
        <Card>
          <CardHeader>
            <CardTitle>Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      ) : !data || data.data.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No Holdings Found</CardTitle>
            <CardDescription>
              No active ETFs hold {upperTicker}, or the pipeline has not been run
              yet.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <section aria-label="ETF holders">
          <h2 className="mb-4 text-xl font-semibold">
            ETF Holders ({data.data.length})
          </h2>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fund</TableHead>
                    <TableHead>Fund Name</TableHead>
                    <TableHead className="text-right">ETF Wt%</TableHead>
                    <TableHead className="text-right">Bench Wt%</TableHead>
                    <TableHead className="text-right">Deviation</TableHead>
                    <TableHead>Direction</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.data.map((holder) => (
                    <TableRow key={holder.fund_ticker}>
                      <TableCell>
                        <Link
                          href={`/funds/${holder.fund_ticker}`}
                          className="font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {holder.fund_ticker}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-xs truncate">
                        {holder.fund_name}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {parseFloat(holder.etf_weight_pct).toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {parseFloat(holder.benchmark_weight_pct).toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium">
                        {formatPct(holder.deviation_pct)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            holder.direction === "overweight"
                              ? "default"
                              : "secondary"
                          }
                        >
                          {holder.direction}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          {data.pagination.has_more && (
            <p className="mt-2 text-sm text-muted-foreground">
              Showing {data.data.length} of {data.pagination.total_count} holders
            </p>
          )}
        </section>
      )}
    </div>
  );
}
