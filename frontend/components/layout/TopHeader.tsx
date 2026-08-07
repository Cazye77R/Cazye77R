"use client";

import Link from "next/link";
import { Search, Settings } from "lucide-react";
import { OPEN_SEARCH_EVENT } from "@/components/layout/SearchModal";
import { cn } from "@/lib/utils";

export default function TopHeader() {
  function openSearch() {
    window.dispatchEvent(new CustomEvent(OPEN_SEARCH_EVENT));
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

        {/* Search trigger – opens global SearchModal */}
        <button
          onClick={openSearch}
          aria-label="Aktie suchen (⌘K)"
          aria-keyshortcuts="Meta+k Control+k"
          className={cn(
            "relative flex flex-1 max-w-md mx-auto items-center gap-2 h-9 rounded-lg border",
            "border-border bg-surface px-3 text-left",
            "hover:border-primary/40 hover:bg-card",
            "transition-colors duration-200",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          )}
        >
          <Search className="size-4 text-foreground-muted shrink-0" aria-hidden />
          <span className="flex-1 text-sm text-foreground-muted">Aktie suchen…</span>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-mono text-foreground-muted select-none">
            ⌘ K
          </kbd>
        </button>

        {/* Settings */}
        <Link
          href="/settings"
          className="shrink-0 flex items-center justify-center size-9 rounded-lg text-foreground-muted hover:text-foreground hover:bg-card transition-colors"
          aria-label="Einstellungen"
        >
          <Settings className="size-5" />
        </Link>

      </div>
    </header>
  );
}
