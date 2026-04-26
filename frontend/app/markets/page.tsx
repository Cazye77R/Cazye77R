"use client";

import { useMemo, useState } from "react";
import type { Stock } from "@/lib/types";
import { STOCKS } from "@/lib/mock-data";
import { Input }     from "@/components/ui/input";
import { cn }        from "@/lib/utils";
import StockList     from "@/components/stock/StockList";
import { Search, ArrowUpDown } from "lucide-react";

const SECTORS = Array.from(new Set(STOCKS.map((s) => s.sector))).sort();

type SortKey = "name" | "price" | "change" | "marketCap" | "volume";
const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "change",    label: "Veränderung" },
  { value: "price",     label: "Kurs" },
  { value: "marketCap", label: "Marktkapitalisierung" },
  { value: "volume",    label: "Volumen" },
  { value: "name",      label: "Name" },
];

export default function MarketsPage() {
  const [query,  setQuery]  = useState("");
  const [sector, setSector] = useState("Alle");
  const [sortBy, setSortBy] = useState<SortKey>("change");
  const [sortAsc, setSortAsc] = useState(false);

  function toggleSort(key: SortKey) {
    if (sortBy === key) {
      setSortAsc((v) => !v);
    } else {
      setSortBy(key);
      setSortAsc(false);
    }
  }

  const filtered = useMemo<Stock[]>(() => {
    let list = STOCKS.filter((s) => {
      const q = query.trim().toLowerCase();
      if (q && !s.ticker.toLowerCase().includes(q) && !s.name.toLowerCase().includes(q))
        return false;
      if (sector !== "Alle" && s.sector !== sector)
        return false;
      return true;
    });

    list = [...list].sort((a, b) => {
      let diff = 0;
      if (sortBy === "name")      diff = a.name.localeCompare(b.name);
      if (sortBy === "price")     diff = a.price     - b.price;
      if (sortBy === "change")    diff = a.changePercent - b.changePercent;
      if (sortBy === "marketCap") diff = a.marketCap  - b.marketCap;
      if (sortBy === "volume")    diff = a.volume     - b.volume;
      return sortAsc ? diff : -diff;
    });

    return list;
  }, [query, sector, sortBy, sortAsc]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 space-y-5">
      <h1 className="text-xl font-bold text-foreground">Märkte</h1>

      {/* ── Filter bar ── */}
      <div className="space-y-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-foreground-muted pointer-events-none" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Suche nach Ticker oder Name…"
            className="pl-9"
            aria-label="Aktie suchen"
          />
        </div>

        {/* Sector chips */}
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Sektor-Filter">
          {["Alle", ...SECTORS].map((s) => (
            <button
              key={s}
              onClick={() => setSector(s)}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-full border transition-all duration-150",
                sector === s
                  ? "bg-primary/15 border-primary/30 text-primary"
                  : "border-border text-foreground-muted hover:text-foreground hover:border-primary/20"
              )}
              aria-pressed={sector === s}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Sort pills */}
        <div className="flex flex-wrap gap-1.5 items-center">
          <ArrowUpDown className="size-3.5 text-foreground-muted shrink-0" aria-hidden />
          {SORT_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => toggleSort(value)}
              className={cn(
                "px-2.5 py-1 text-xs font-medium rounded-md border transition-all duration-150",
                sortBy === value
                  ? "bg-accent/15 border-accent/30 text-accent"
                  : "border-border text-foreground-muted hover:text-foreground hover:border-accent/20"
              )}
              aria-pressed={sortBy === value}
            >
              {label}
              {sortBy === value && (
                <span className="ml-1">{sortAsc ? "↑" : "↓"}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Results count ── */}
      <p className="text-xs text-foreground-muted">
        {filtered.length} von {STOCKS.length} Aktien
      </p>

      {/* ── Stock list ── */}
      <StockList stocks={filtered} variant="compact" initialCount={12} />
    </div>
  );
}
