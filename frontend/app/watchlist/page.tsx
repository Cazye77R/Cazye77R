"use client";

import { useState } from "react";
import Link         from "next/link";
import { Plus, Trash2, ArrowUpDown } from "lucide-react";
import { useWatchlistStore } from "@/store/watchlist-store";
import { STOCKS }            from "@/lib/mock-data";
import type { Stock }        from "@/lib/types";
import { formatPrice }       from "@/lib/format";
import { cn }                from "@/lib/utils";
import StockCard             from "@/components/stock/StockCard";
import { Button }            from "@/components/ui/button";

type SortMode = "alpha" | "perf";

export default function WatchlistPage() {
  const { tickers, remove, clear } = useWatchlistStore();
  const [sort, setSort] = useState<SortMode>("perf");

  const stocks = tickers
    .map((t) => STOCKS.find((s) => s.ticker === t))
    .filter((s): s is Stock => s !== undefined);

  const sorted = [...stocks].sort((a, b) =>
    sort === "alpha"
      ? a.ticker.localeCompare(b.ticker)
      : b.changePercent - a.changePercent
  );

  // ── Empty state ────────────────────────────────────────────────────────────
  if (tickers.length === 0) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 flex flex-col items-center gap-6 text-center">
        <span className="text-6xl" aria-hidden>⭐</span>
        <div>
          <h1 className="text-xl font-bold text-foreground">Watchlist ist leer</h1>
          <p className="text-sm text-foreground-muted mt-2">
            Füge Aktien hinzu, um sie hier zu verfolgen.
          </p>
        </div>
        <Button asChild size="lg" className="gap-2">
          <Link href="/markets">
            <Plus className="size-5" />
            Erste Aktie hinzufügen
          </Link>
        </Button>
      </div>
    );
  }

  // ── Populated state ────────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-2xl px-4 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Watchlist</h1>
          <p className="text-sm text-foreground-muted">{tickers.length} Aktien</p>
        </div>
        <Link
          href="/markets"
          className="flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
          aria-label="Aktie hinzufügen"
        >
          <Plus className="size-4" />
          Hinzufügen
        </Link>
      </div>

      {/* Sort controls */}
      <div className="flex items-center gap-2">
        <ArrowUpDown className="size-3.5 text-foreground-muted shrink-0" aria-hidden />
        {(
          [
            { value: "perf",  label: "Performance" },
            { value: "alpha", label: "Alphabetisch" },
          ] as { value: SortMode; label: string }[]
        ).map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setSort(value)}
            aria-pressed={sort === value}
            className={cn(
              "px-2.5 py-1 text-xs font-medium rounded-md border transition-all duration-150",
              sort === value
                ? "bg-primary/15 border-primary/30 text-primary"
                : "border-border text-foreground-muted hover:text-foreground hover:bg-card"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* List */}
      <ul className="space-y-2" role="list" aria-label="Watchlist">
        {sorted.map((stock) => (
          <li key={stock.ticker} className="flex items-center gap-2">
            <div className="flex-1 min-w-0">
              <StockCard stock={stock} variant="compact" />
            </div>
            <button
              onClick={() => remove(stock.ticker)}
              aria-label={`${stock.ticker} entfernen`}
              className="shrink-0 flex items-center justify-center size-9 rounded-lg border border-border text-foreground-muted hover:text-danger hover:border-danger/30 hover:bg-danger/10 transition-all duration-200"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </li>
        ))}
      </ul>

      {/* Performance summary */}
      <div className="rounded-xl border border-border bg-surface p-4">
        <p className="text-xs text-foreground-muted mb-3">Performance heute</p>
        <div className="space-y-2">
          {sorted.slice(0, 3).map((s) => (
            <div key={s.ticker} className="flex items-center justify-between text-sm">
              <span className="font-semibold text-foreground">{s.ticker}</span>
              <span className="font-mono text-foreground">{formatPrice(s.price)}</span>
              <span
                className={cn(
                  "font-mono text-xs",
                  s.changePercent >= 0 ? "text-success" : "text-danger"
                )}
              >
                {s.changePercent >= 0 ? "+" : ""}
                {(s.changePercent * 100).toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Clear all */}
      <button
        onClick={() => {
          if (window.confirm("Watchlist wirklich leeren?")) clear();
        }}
        className="w-full text-xs text-foreground-muted hover:text-danger transition-colors py-2"
      >
        Watchlist leeren
      </button>
    </div>
  );
}
