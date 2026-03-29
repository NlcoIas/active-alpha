"use client";

import { useState } from "react";
import Link from "next/link";
import { api, type StockHoldersResponse } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Search } from "lucide-react";

function formatPct(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
}

export default function StocksPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StockHoldersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const ticker = query.trim().toUpperCase();
    if (!ticker) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setSearched(true);

    try {
      const data = await api.getStockHolders(ticker);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load stock data"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Stock Lookup
        </h1>
        <p className="mt-1 text-muted-foreground">
          Search for a stock to see which active ETFs hold it
        </p>
      </div>

      <form
        onSubmit={handleSearch}
        className="mb-8 flex items-end gap-2"
      >
        <div className="flex-1 max-w-sm">
          <label htmlFor="stock-search" className="mb-1.5 block text-sm font-medium">
            Stock Ticker
          </label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="stock-search"
              placeholder="e.g. AAPL, MSFT, TSLA"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-8"
            />
          </div>
        </div>
        <Button type="submit" disabled={!query.trim() || loading}>
          {loading ? "Searching..." : "Search"}
        </Button>
      </form>

      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}

      {error && (
        <Card>
          <CardHeader>
            <CardTitle>Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      )}

      {result && (
        <section aria-label="Stock holders">
          <div className="mb-4">
            <h2 className="text-xl font-semibold">
              <Link
                href={`/stocks/${result.stock_ticker}`}
                className="text-primary underline-offset-4 hover:underline"
              >
                {result.stock_ticker}
              </Link>
            </h2>
            <p className="text-sm text-muted-foreground">
              Snapshot: {result.snapshot_date}
            </p>
          </div>

          {result.data.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Not Found</CardTitle>
                <CardDescription>
                  No active ETFs hold this stock, or the ticker may not exist.
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
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
                    {result.data.map((holder) => (
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
          )}
        </section>
      )}

      {searched && !loading && !result && !error && (
        <p className="text-center text-muted-foreground">No results found.</p>
      )}
    </div>
  );
}
