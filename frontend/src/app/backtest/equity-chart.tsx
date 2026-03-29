"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

type EquityCurveData = {
  date: string;
  value: number;
  benchmark: number;
};

type EquityCurveChartProps = {
  data: EquityCurveData[];
};

export function EquityCurveChart({ data }: EquityCurveChartProps) {
  // Sample data to avoid rendering thousands of points
  const sampled = sampleData(data, 200);

  return (
    <div className="h-72 w-full sm:h-80 lg:h-96">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={sampled}
          margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            className="stroke-border"
          />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickFormatter={(value: string) => {
              const d = new Date(value);
              return `${d.getMonth() + 1}/${String(d.getFullYear()).slice(2)}`;
            }}
            interval="preserveStartEnd"
            className="text-muted-foreground"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(value: number) => value.toFixed(2)}
            className="text-muted-foreground"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            labelFormatter={(label) => `Date: ${String(label)}`}
            formatter={(value, name) => [
              Number(value).toFixed(4),
              String(name) === "value" ? "Strategy" : "Benchmark",
            ]}
          />
          <Legend
            formatter={(value: string) =>
              value === "value" ? "Strategy" : "Benchmark"
            }
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            name="value"
          />
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke="hsl(var(--muted-foreground))"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={false}
            name="benchmark"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function sampleData<T>(data: T[], maxPoints: number): T[] {
  if (data.length <= maxPoints) return data;
  const step = data.length / maxPoints;
  const result: T[] = [];
  for (let i = 0; i < data.length; i += step) {
    result.push(data[Math.floor(i)]);
  }
  // Always include last point
  const last = data[data.length - 1];
  if (result[result.length - 1] !== last) {
    result.push(last);
  }
  return result;
}
