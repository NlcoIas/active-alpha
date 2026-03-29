import { Skeleton } from "@/components/ui/skeleton";

export default function BacktestLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Skeleton className="mb-2 h-8 w-48" />
      <Skeleton className="mb-8 h-4 w-64" />
      <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
        <Skeleton className="h-[600px] w-full rounded-xl" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    </div>
  );
}
