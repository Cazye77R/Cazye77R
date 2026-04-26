import Link from "next/link";
import { cn } from "@/lib/utils";
import { formatPrice, formatLargeNumber } from "@/lib/format";
import type { Stock } from "@/lib/types";
import { getCandles } from "@/lib/mock-data";
import GlowCard     from "@/components/shared/GlowCard";
import ChangeBadge  from "@/components/shared/ChangeBadge";
import MiniSparkline from "@/components/charts/MiniSparkline";

interface StockCardProps {
  stock:    Stock;
  variant?: "compact" | "detailed" | "trending";
  className?: string;
}

export default function StockCard({
  stock,
  variant = "compact",
  className,
}: StockCardProps) {
  const candles = getCandles(stock.ticker, 30);
  const isUp    = stock.changePercent >= 0;

  // ── Compact (Watchlist / list rows) ──────────────────────────────────────
  if (variant === "compact") {
    return (
      <Link href={`/stock/${stock.ticker}`} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl">
        <GlowCard
          glow="primary"
          className={cn("flex items-center gap-3 px-4 py-3", className)}
        >
          {/* Logo */}
          <span className="text-2xl shrink-0" aria-hidden>{stock.logo ?? "📈"}</span>

          {/* Name + sector */}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-foreground leading-tight">{stock.ticker}</p>
            <p className="text-xs text-foreground-muted truncate">{stock.name}</p>
          </div>

          {/* Sparkline */}
          <div className="w-20 shrink-0">
            <MiniSparkline candles={candles} days={30} height={36} />
          </div>

          {/* Price + change */}
          <div className="text-right shrink-0">
            <p className="text-sm font-mono font-semibold text-foreground">
              {formatPrice(stock.price)}
            </p>
            <ChangeBadge value={stock.changePercent} variant="compact" />
          </div>
        </GlowCard>
      </Link>
    );
  }

  // ── Detailed ──────────────────────────────────────────────────────────────
  if (variant === "detailed") {
    return (
      <Link href={`/stock/${stock.ticker}`} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl">
        <GlowCard
          glow="primary"
          className={cn("flex flex-col gap-3 p-4", className)}
        >
          {/* Header row */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-2xl shrink-0" aria-hidden>{stock.logo ?? "📈"}</span>
              <div className="min-w-0">
                <p className="text-sm font-bold text-foreground">{stock.ticker}</p>
                <p className="text-xs text-foreground-muted truncate">{stock.name}</p>
              </div>
            </div>
            <ChangeBadge value={stock.changePercent} variant="compact" />
          </div>

          {/* Sparkline */}
          <MiniSparkline candles={candles} days={30} height={48} />

          {/* Price */}
          <p
            className={cn(
              "text-xl font-mono font-bold",
              isUp ? "text-success" : "text-danger"
            )}
          >
            {formatPrice(stock.price)}
          </p>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-foreground-muted">Market Cap</span>
            <span className="font-mono text-foreground text-right">
              {formatLargeNumber(stock.marketCap)}
            </span>
            <span className="text-foreground-muted">Volume</span>
            <span className="font-mono text-foreground text-right">
              {formatLargeNumber(stock.volume)}
            </span>
            <span className="text-foreground-muted">Sector</span>
            <span className="text-foreground text-right truncate">{stock.sector}</span>
          </div>
        </GlowCard>
      </Link>
    );
  }

  // ── Trending ──────────────────────────────────────────────────────────────
  return (
    <Link href={`/stock/${stock.ticker}`} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl">
      <GlowCard
        glow="primary"
        className={cn("relative flex flex-col gap-2 p-4 overflow-hidden", className)}
      >
        {/* Trending badge */}
        <span className="absolute top-3 right-3 text-[10px] font-semibold bg-primary/15 text-primary border border-primary/20 rounded-full px-2 py-0.5">
          🔥 Trending
        </span>

        {/* Logo + ticker */}
        <div className="flex items-center gap-2">
          <span className="text-3xl" aria-hidden>{stock.logo ?? "📈"}</span>
          <div>
            <p className="text-base font-bold text-foreground">{stock.ticker}</p>
            <p className="text-xs text-foreground-muted">{stock.sector}</p>
          </div>
        </div>

        {/* Sparkline */}
        <MiniSparkline candles={candles} days={30} height={52} />

        {/* Price + change */}
        <div className="flex items-end justify-between">
          <p className={cn("text-xl font-mono font-bold", isUp ? "text-success" : "text-danger")}>
            {formatPrice(stock.price)}
          </p>
          <ChangeBadge value={stock.changePercent} variant="full" />
        </div>

        {/* Market cap */}
        <p className="text-xs text-foreground-muted">
          Cap <span className="text-foreground font-mono">{formatLargeNumber(stock.marketCap)}</span>
        </p>
      </GlowCard>
    </Link>
  );
}
