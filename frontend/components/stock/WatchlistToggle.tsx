"use client";

import { Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWatchlistStore } from "@/store/watchlist-store";

interface WatchlistToggleProps {
  ticker: string;
  className?: string;
}

export default function WatchlistToggle({ ticker, className }: WatchlistToggleProps) {
  const { has, toggle } = useWatchlistStore();
  const inList = has(ticker);

  return (
    <button
      onClick={() => toggle(ticker)}
      aria-label={inList ? `${ticker} aus Watchlist entfernen` : `${ticker} zur Watchlist hinzufügen`}
      aria-pressed={inList}
      className={cn(
        "flex items-center justify-center size-10 rounded-xl border transition-all duration-200",
        inList
          ? "bg-primary/15 border-primary/30 text-primary hover:bg-primary/25 shadow-[0_0_12px_-3px_rgba(0,212,255,0.4)]"
          : "border-border bg-surface text-foreground-muted hover:border-primary/30 hover:text-foreground hover:bg-card",
        className
      )}
    >
      <Star
        className={cn("size-5 transition-all duration-200", inList && "fill-primary")}
        aria-hidden
      />
    </button>
  );
}
