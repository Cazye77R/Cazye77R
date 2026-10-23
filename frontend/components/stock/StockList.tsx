"use client";

import { useState } from "react";
import type { Stock } from "@/lib/types";
import StockCard     from "./StockCard";
import AnimatedList  from "@/components/shared/AnimatedList";

interface StockListProps {
  stocks: Stock[];
  variant?: "compact" | "detailed";
  /**
   * Items to show before "Load more".
   * Virtualization via @tanstack/react-virtual would be added when
   * real API data exceeds 50+ items. For now uses progressive disclosure.
   */
  initialCount?: number;
  className?: string;
}

export default function StockList({
  stocks,
  variant = "compact",
  initialCount = 20,
  className,
}: StockListProps) {
  const [visibleCount, setVisibleCount] = useState(initialCount);
  const visible = stocks.slice(0, visibleCount);
  const hasMore = visibleCount < stocks.length;

  if (!stocks.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
        <span className="text-4xl" aria-hidden>📭</span>
        <p className="text-foreground-muted text-sm">Keine Aktien gefunden.</p>
      </div>
    );
  }

  return (
    <div className={className}>
      <AnimatedList className="space-y-2" aria-label="Stock list">
        {visible.map((stock) => (
          <StockCard key={stock.ticker} stock={stock} variant={variant} />
        ))}
      </AnimatedList>

      {hasMore && (
        <button
          onClick={() => setVisibleCount((c) => c + initialCount)}
          className="mt-4 w-full rounded-xl border border-border bg-surface py-3 text-sm font-medium text-foreground-muted hover:text-foreground hover:bg-card transition-colors"
        >
          Weitere {Math.min(initialCount, stocks.length - visibleCount)} anzeigen
        </button>
      )}
    </div>
  );
}
