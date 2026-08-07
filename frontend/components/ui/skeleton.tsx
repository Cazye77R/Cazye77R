import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Applies rounded-full (circle/pill) instead of rounded-lg */
  rounded?: boolean;
}

export function Skeleton({ className, rounded, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "shimmer",
        rounded ? "rounded-full" : "rounded-lg",
        className
      )}
      aria-hidden
      {...props}
    />
  );
}

/** Pre-built skeleton that matches StockCard variant="compact" */
export function StockCardSkeleton() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
      <Skeleton rounded className="size-9 shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-16" />
        <Skeleton className="h-2.5 w-28" />
      </div>
      <Skeleton className="h-9 w-20" />
      <div className="text-right space-y-2">
        <Skeleton className="h-4 w-16 ml-auto" />
        <Skeleton className="h-5 w-14 ml-auto rounded-full" />
      </div>
    </div>
  );
}

/** Stack of N StockCardSkeletons */
export function StockListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-2" aria-label="Lädt…" aria-busy>
      {Array.from({ length: count }).map((_, i) => (
        <StockCardSkeleton key={i} />
      ))}
    </div>
  );
}
