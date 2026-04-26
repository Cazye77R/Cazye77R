"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Search, Settings, X } from "lucide-react";
import { STOCKS } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export default function TopHeader() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const isMac =
    typeof navigator !== "undefined" && navigator.platform.startsWith("Mac");

  // Cmd/Ctrl+K to focus search
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (e.key === "Escape") {
        setQuery("");
        setOpen(false);
        inputRef.current?.blur();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function onPointer(e: PointerEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, []);

  const results = query.trim().length >= 1
    ? STOCKS.filter(
        (s) =>
          s.ticker.toLowerCase().includes(query.toLowerCase()) ||
          s.name.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 6)
    : [];

  function navigate(ticker: string) {
    router.push(`/stock/${ticker}`);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  }

  return (
    <header className="sticky top-0 z-50 w-full glass border-b border-border/60">
      <div className="mx-auto flex h-14 max-w-5xl items-center gap-4 px-4">
        {/* Logo */}
        <Link
          href="/"
          className="shrink-0 text-lg font-bold tracking-tight bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent hover:opacity-80 transition-opacity"
          aria-label="StockMind home"
        >
          StockMind
        </Link>

        {/* Search */}
        <div ref={containerRef} className="relative flex-1 max-w-md mx-auto">
          <div
            className={cn(
              "flex items-center gap-2 h-9 rounded-lg border bg-surface px-3",
              "transition-colors duration-200",
              open
                ? "border-primary/50 ring-1 ring-primary/20"
                : "border-border hover:border-primary/30"
            )}
          >
            <Search className="size-4 text-foreground-muted shrink-0" aria-hidden />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setOpen(e.target.value.length > 0);
              }}
              onFocus={() => query.length > 0 && setOpen(true)}
              placeholder="Aktie suchen…"
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-foreground-muted outline-none"
              aria-label="Search stocks"
              aria-expanded={open && results.length > 0}
              aria-haspopup="listbox"
              autoComplete="off"
            />
            {query ? (
              <button
                onClick={() => { setQuery(""); setOpen(false); }}
                className="text-foreground-muted hover:text-foreground transition-colors"
                aria-label="Clear search"
              >
                <X className="size-3.5" />
              </button>
            ) : (
              <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-mono text-foreground-muted select-none">
                {isMac ? "⌘" : "Ctrl"} K
              </kbd>
            )}
          </div>

          {/* Dropdown results */}
          {open && results.length > 0 && (
            <ul
              role="listbox"
              className="absolute top-full left-0 right-0 mt-1.5 overflow-hidden rounded-lg border border-border bg-card shadow-xl z-50"
            >
              {results.map((s) => (
                <li key={s.ticker} role="option" aria-selected={false}>
                  <button
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-surface transition-colors"
                    onClick={() => navigate(s.ticker)}
                  >
                    <span className="text-base" aria-hidden>{s.logo}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-foreground">{s.ticker}</p>
                      <p className="text-xs text-foreground-muted truncate">{s.name}</p>
                    </div>
                    <span className="ml-auto text-sm font-mono text-foreground-muted">
                      ${s.price.toFixed(2)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Settings icon */}
        <Link
          href="/settings"
          className="shrink-0 flex items-center justify-center size-9 rounded-lg text-foreground-muted hover:text-foreground hover:bg-card transition-colors"
          aria-label="Settings"
        >
          <Settings className="size-5" />
        </Link>
      </div>
    </header>
  );
}
