"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { api, type BacktestResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { BacktestResults } from "./results";

const backtestSchema = z.object({
  benchmark_ticker: z.string(),
  top_n: z.number().min(1).max(20),
  rebalance_frequency: z.enum(["daily", "weekly", "monthly"]),
  holding_period_days: z.number().min(1).max(365),
  min_deviation_pct: z.number().min(0).max(100),
  weighting: z.enum(["equal", "deviation_weighted"]),
  lookback_years: z.number().min(1).max(5),
  direction: z.enum(["long", "short", "long_short"]),
  transaction_cost_bps: z.number().min(0).max(100),
});

type BacktestFormValues = z.infer<typeof backtestSchema>;

const defaultValues: BacktestFormValues = {
  benchmark_ticker: "SPY",
  top_n: 10,
  rebalance_frequency: "weekly",
  holding_period_days: 5,
  min_deviation_pct: 0.5,
  weighting: "equal",
  lookback_years: 3,
  direction: "long",
  transaction_cost_bps: 10,
};

export default function BacktestPage() {
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const form = useForm<BacktestFormValues>({
    defaultValues,
  });

  async function onSubmit(values: BacktestFormValues) {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await api.runBacktest(values);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Backtest failed"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Backtest Lab
        </h1>
        <p className="mt-1 text-muted-foreground">
          Test deviation-based trading strategies
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Parameters</CardTitle>
            <CardDescription>
              Configure your backtest strategy
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-4"
            >
              <div>
                <label
                  htmlFor="benchmark_ticker"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Benchmark
                </label>
                <Select
                  value={form.watch("benchmark_ticker")}
                  onValueChange={(val) => {
                    if (val) form.setValue("benchmark_ticker", val);
                  }}
                >
                  <SelectTrigger id="benchmark_ticker" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="SPY">SPY (S&amp;P 500)</SelectItem>
                    <SelectItem value="QQQ">QQQ (Nasdaq 100)</SelectItem>
                    <SelectItem value="IWM">IWM (Russell 2000)</SelectItem>
                    <SelectItem value="VTI">VTI (Total Market)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label
                  htmlFor="top_n"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Top N Stocks
                </label>
                <Input
                  id="top_n"
                  type="number"
                  min={1}
                  max={20}
                  {...form.register("top_n", { valueAsNumber: true })}
                />
              </div>

              <div>
                <label
                  htmlFor="rebalance_frequency"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Rebalance Frequency
                </label>
                <Select
                  value={form.watch("rebalance_frequency")}
                  onValueChange={(val) => {
                    if (val)
                      form.setValue(
                        "rebalance_frequency",
                        val as "daily" | "weekly" | "monthly"
                      );
                  }}
                >
                  <SelectTrigger id="rebalance_frequency" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label
                  htmlFor="holding_period_days"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Holding Period (days)
                </label>
                <Input
                  id="holding_period_days"
                  type="number"
                  min={1}
                  max={365}
                  {...form.register("holding_period_days", {
                    valueAsNumber: true,
                  })}
                />
              </div>

              <div>
                <label
                  htmlFor="min_deviation_pct"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Min Deviation (%)
                </label>
                <Input
                  id="min_deviation_pct"
                  type="number"
                  step="0.1"
                  min={0}
                  max={100}
                  {...form.register("min_deviation_pct", {
                    valueAsNumber: true,
                  })}
                />
              </div>

              <div>
                <label
                  htmlFor="weighting"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Weighting
                </label>
                <Select
                  value={form.watch("weighting")}
                  onValueChange={(val) => {
                    if (val)
                      form.setValue(
                        "weighting",
                        val as "equal" | "deviation_weighted"
                      );
                  }}
                >
                  <SelectTrigger id="weighting" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="equal">Equal Weight</SelectItem>
                    <SelectItem value="deviation_weighted">
                      Deviation Weighted
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label
                  htmlFor="lookback_years"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Lookback Period
                </label>
                <Select
                  value={String(form.watch("lookback_years"))}
                  onValueChange={(val) => {
                    if (val) form.setValue("lookback_years", Number(val));
                  }}
                >
                  <SelectTrigger id="lookback_years" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 Year</SelectItem>
                    <SelectItem value="2">2 Years</SelectItem>
                    <SelectItem value="3">3 Years</SelectItem>
                    <SelectItem value="5">5 Years</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label
                  htmlFor="direction"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Direction
                </label>
                <Select
                  value={form.watch("direction")}
                  onValueChange={(val) => {
                    if (val)
                      form.setValue(
                        "direction",
                        val as "long" | "short" | "long_short"
                      );
                  }}
                >
                  <SelectTrigger id="direction" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="long">Long Only</SelectItem>
                    <SelectItem value="short">Short Only</SelectItem>
                    <SelectItem value="long_short">Long-Short</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label
                  htmlFor="transaction_cost_bps"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Transaction Costs (bps)
                </label>
                <Input
                  id="transaction_cost_bps"
                  type="number"
                  min={0}
                  max={100}
                  {...form.register("transaction_cost_bps", {
                    valueAsNumber: true,
                  })}
                />
              </div>

              <Separator />

              <Button
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading ? "Running Backtest..." : "Run Backtest"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div>
          {loading && (
            <div className="space-y-4">
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-64 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          )}

          {error && (
            <Card>
              <CardHeader>
                <CardTitle>Backtest Error</CardTitle>
                <CardDescription>{error}</CardDescription>
              </CardHeader>
            </Card>
          )}

          {result && <BacktestResults result={result} />}

          {!loading && !error && !result && (
            <div className="flex items-center justify-center rounded-lg border border-dashed py-20 text-muted-foreground">
              <p>Configure parameters and run a backtest to see results.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
