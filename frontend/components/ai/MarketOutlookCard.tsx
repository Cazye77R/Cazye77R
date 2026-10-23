import type { MarketOutlook } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MarketOutlookCardProps {
  outlook: MarketOutlook;
}

const SENTIMENT_CONFIG = {
  bullish: {
    color:   "text-success",
    bg:      "bg-success/10",
    border:  "border-success/20",
    glow:    "shadow-[0_0_40px_-10px_rgba(0,255,136,0.3)]",
    Icon:    TrendingUp,
    label:   "Bullish",
  },
  bearish: {
    color:   "text-danger",
    bg:      "bg-danger/10",
    border:  "border-danger/20",
    glow:    "shadow-[0_0_40px_-10px_rgba(255,59,59,0.3)]",
    Icon:    TrendingDown,
    label:   "Bearish",
  },
  neutral: {
    color:   "text-accent",
    bg:      "bg-accent/10",
    border:  "border-accent/20",
    glow:    "shadow-[0_0_40px_-10px_rgba(108,99,255,0.3)]",
    Icon:    Minus,
    label:   "Neutral",
  },
} as const;

export default function MarketOutlookCard({ outlook }: MarketOutlookCardProps) {
  const cfg = SENTIMENT_CONFIG[outlook.sentiment];
  const { Icon } = cfg;
  const pct = Math.round(outlook.confidence * 100);

  return (
    <div
      className={cn(
        "glass rounded-2xl border p-5 space-y-4",
        cfg.border,
        cfg.glow
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "flex items-center justify-center size-9 rounded-xl",
              cfg.bg
            )}
          >
            <Icon className={cn("size-5", cfg.color)} aria-hidden />
          </span>
          <div>
            <p className="text-xs text-foreground-muted">Market Outlook</p>
            <p className={cn("text-sm font-bold", cfg.color)}>{cfg.label}</p>
          </div>
        </div>

        {/* Confidence pill */}
        <span
          className={cn(
            "text-xs font-semibold font-mono px-2.5 py-1 rounded-full border",
            cfg.bg,
            cfg.border,
            cfg.color
          )}
        >
          {pct}% confidence
        </span>
      </div>

      {/* Confidence bar */}
      <div className="h-1.5 w-full rounded-full bg-border overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", {
            "bg-success": outlook.sentiment === "bullish",
            "bg-danger":  outlook.sentiment === "bearish",
            "bg-accent":  outlook.sentiment === "neutral",
          })}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Summary */}
      <p className="text-sm text-foreground leading-relaxed">{outlook.summary}</p>

      {/* Timestamp */}
      <p className="text-xs text-foreground-muted">
        Updated {formatRelativeTime(outlook.updatedAt)}
      </p>
    </div>
  );
}
