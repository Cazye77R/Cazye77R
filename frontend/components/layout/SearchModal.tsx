"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter }                         from "next/navigation";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "cmdk";
import { TrendingUp, TrendingDown, Star } from "lucide-react";
import { STOCKS, TRENDING_STOCKS }        from "@/lib/mock-data";
import { formatPrice }                    from "@/lib/format";
import { cn }                             from "@/lib/utils";
import { useWatchlistStore }              from "@/store/watchlist-store";

/** Dispatch this event from anywhere to open the search modal. */
export const OPEN_SEARCH_EVENT = "stockmind:open-search";

export default function SearchModal() {
  const [open, setOpen] = useState(false);
  const router          = useRouter();
  const { has }         = useWatchlistStore();

  // Global keyboard shortcut + custom event listener
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    function onCustomEvent() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_SEARCH_EVENT, onCustomEvent);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_SEARCH_EVENT, onCustomEvent);
    };
  }, []);

  const navigate = useCallback(
    (ticker: string) => {
      setOpen(false);
      router.push(`/stock/${ticker}`);
    },
    [router]
  );

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      overlayClassName="fixed inset-0 z-[80] bg-black/60 backdrop-blur-sm"
      contentClassName={cn(
        "fixed left-1/2 top-[20%] z-[90] w-full max-w-md -translate-x-1/2",
        "overflow-hidden rounded-2xl border border-border",
        "bg-card shadow-2xl shadow-black/40",
        "focus:outline-none"
      )}
      label="Global stock search"
      loop
    >
      {/* Input */}
      <div className="flex items-center border-b border-border px-4 py-3">
        <CommandInput
          placeholder="Aktie suchen – Ticker oder Name…"
          className={cn(
            "flex-1 bg-transparent text-sm text-foreground placeholder:text-foreground-muted",
            "outline-none border-none"
          )}
          autoFocus
        />
        <kbd className="ml-3 shrink-0 text-[10px] font-mono text-foreground-muted border border-border rounded px-1.5 py-0.5">
          ESC
        </kbd>
      </div>

      <CommandList className="max-h-80 overflow-y-auto py-2">
        <CommandEmpty className="py-8 text-center text-sm text-foreground-muted">
          Keine Ergebnisse gefunden.
        </CommandEmpty>

        {/* Trending section */}
        <CommandGroup
          heading={
            <span className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-foreground-muted">
              Trending
            </span>
          }
        >
          {TRENDING_STOCKS.slice(0, 3).map((s) => (
            <SearchItem
              key={s.ticker}
              ticker={s.ticker}
              name={s.name}
              logo={s.logo}
              price={s.price}
              changePercent={s.changePercent}
              inWatchlist={has(s.ticker)}
              onSelect={navigate}
            />
          ))}
        </CommandGroup>

        {/* All stocks */}
        <CommandGroup
          heading={
            <span className="px-4 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-foreground-muted">
              Alle Aktien
            </span>
          }
        >
          {STOCKS.map((s) => (
            <SearchItem
              key={s.ticker}
              ticker={s.ticker}
              name={s.name}
              logo={s.logo}
              price={s.price}
              changePercent={s.changePercent}
              inWatchlist={has(s.ticker)}
              onSelect={navigate}
            />
          ))}
        </CommandGroup>
      </CommandList>

      {/* Footer hint */}
      <div className="flex items-center gap-3 border-t border-border px-4 py-2">
        <span className="text-[10px] text-foreground-muted">
          <kbd className="font-mono border border-border rounded px-1">↑↓</kbd> navigieren
        </span>
        <span className="text-[10px] text-foreground-muted">
          <kbd className="font-mono border border-border rounded px-1">↵</kbd> öffnen
        </span>
        <span className="text-[10px] text-foreground-muted ml-auto">
          <kbd className="font-mono border border-border rounded px-1">⌘K</kbd> schließen
        </span>
      </div>
    </CommandDialog>
  );
}

// ── Search result item ────────────────────────────────────────────────────────

interface SearchItemProps {
  ticker:        string;
  name:          string;
  logo?:         string;
  price:         number;
  changePercent: number;
  inWatchlist:   boolean;
  onSelect:      (ticker: string) => void;
}

function SearchItem({
  ticker,
  name,
  logo,
  price,
  changePercent,
  inWatchlist,
  onSelect,
}: SearchItemProps) {
  const isUp = changePercent >= 0;
  const Icon = isUp ? TrendingUp : TrendingDown;

  return (
    <CommandItem
      value={`${ticker} ${name}`}
      onSelect={() => onSelect(ticker)}
      className={cn(
        "flex items-center gap-3 px-4 py-2.5 cursor-pointer",
        "text-sm transition-colors duration-100",
        "aria-selected:bg-primary/10 aria-selected:text-foreground",
        "data-[selected=true]:bg-primary/10",
        "hover:bg-surface"
      )}
    >
      <span className="text-xl shrink-0" aria-hidden>{logo ?? "📈"}</span>

      <div className="flex-1 min-w-0">
        <span className="font-semibold text-foreground">{ticker}</span>
        <span className="ml-2 text-xs text-foreground-muted truncate">{name}</span>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {inWatchlist && (
          <Star className="size-3 fill-primary text-primary" aria-label="In Watchlist" />
        )}
        <span className="font-mono text-xs text-foreground">{formatPrice(price)}</span>
        <span
          className={cn(
            "flex items-center gap-0.5 text-xs font-mono",
            isUp ? "text-success" : "text-danger"
          )}
        >
          <Icon className="size-3" aria-hidden />
          {isUp ? "+" : ""}{(changePercent * 100).toFixed(2)}%
        </span>
      </div>
    </CommandItem>
  );
}
