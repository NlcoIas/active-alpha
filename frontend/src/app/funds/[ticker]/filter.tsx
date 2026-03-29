"use client";

import { useRouter } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type FundDeviationFilterProps = {
  currentDirection: string;
  ticker: string;
};

export function FundDeviationFilter({
  currentDirection,
  ticker,
}: FundDeviationFilterProps) {
  const router = useRouter();

  function handleChange(value: string | null) {
    if (!value) return;
    const params = new URLSearchParams();
    if (value !== "all") {
      params.set("direction", value);
    }
    const qs = params.toString();
    router.push(`/funds/${ticker}${qs ? `?${qs}` : ""}`);
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="direction-filter" className="text-sm text-muted-foreground">
        Direction:
      </label>
      <Select value={currentDirection} onValueChange={handleChange}>
        <SelectTrigger className="w-40" id="direction-filter">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All</SelectItem>
          <SelectItem value="overweight">Overweight</SelectItem>
          <SelectItem value="underweight">Underweight</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
