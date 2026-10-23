"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useWatchlistStore } from "@/store/watchlist-store";
import { getAllStocks } from "@/lib/api/stocks";
import StockCard from "@/components/stock/StockCard";

export default function WatchlistPreview() {
  // Selectors: subscribe only to the slices this component actually uses.
  const tickers = useWatchlistStore((s) => s.tickers);
  const hasHydrated = useWatchlistStore((s) => s.hasHydrated);
  const stocks = tickers
    .map((t) => getAllStocks().find((s) => s.ticker === t))
    .filter((s): s is NonNullable<typeof s> => s !== undefined)
    .slice(0, 3);

  // Before rehydration completes, `tickers` is still the store's default
  // seed list — render nothing rather than that placeholder list, to
  // avoid a visible flash from (default 3 stocks) → (real watchlist).
  if (!hasHydrated) {
    return (
      <div className="space-y-2" aria-hidden>
        <div className="h-16 rounded-xl border border-border bg-surface animate-pulse" />
      </div>
    );
  }

  if (!stocks.length) {
    return (
      <div className="rounded-xl border border-border bg-surface px-4 py-6 text-center">
        <p className="text-foreground-muted text-sm">Watchlist ist leer.</p>
        <Link
          href="/markets"
          className="mt-2 inline-flex items-center gap-1 text-sm text-primary hover:text-primary/80 transition-colors"
        >
          Aktien entdecken <ArrowRight className="size-3.5" />
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {stocks.map((s) => (
        <StockCard key={s.ticker} stock={s} variant="compact" />
      ))}
      <Link
        href="/watchlist"
        className="flex items-center justify-center gap-1.5 rounded-xl border border-border bg-surface py-2.5 text-sm font-medium text-foreground-muted hover:text-foreground hover:bg-card transition-colors"
      >
        Alle ansehen <ArrowRight className="size-4" />
      </Link>
    </div>
  );
}
