"use client";

import { motion } from "framer-motion";
import { Star }   from "lucide-react";
import { toast }  from "sonner";
import { cn }     from "@/lib/utils";
import { useWatchlistStore } from "@/store/watchlist-store";

interface WatchlistToggleProps {
  ticker: string;
  className?: string;
}

export default function WatchlistToggle({ ticker, className }: WatchlistToggleProps) {
  const { has, toggle } = useWatchlistStore();
  const inList = has(ticker);

  function handleClick() {
    toggle(ticker);
    if (inList) {
      toast(`${ticker} aus Watchlist entfernt`, {
        icon: "⭐",
        duration: 2500,
      });
    } else {
      toast.success(`${ticker} zur Watchlist hinzugefügt`, {
        duration: 2500,
        action: {
          label: "Anzeigen",
          onClick: () => (window.location.href = "/watchlist"),
        },
      });
    }
  }

  return (
    <button
      onClick={handleClick}
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
      {/* Bouncing star animation on toggle */}
      <motion.span
        animate={
          inList
            ? { scale: [1, 1.45, 0.85, 1.15, 1], rotate: [0, -12, 8, -4, 0] }
            : { scale: 1, rotate: 0 }
        }
        transition={{ type: "spring", stiffness: 400, damping: 12, duration: 0.5 }}
        className="flex items-center justify-center"
      >
        <Star
          className={cn(
            "size-5 transition-all duration-200",
            inList && "fill-primary"
          )}
          aria-hidden
        />
      </motion.span>
    </button>
  );
}
