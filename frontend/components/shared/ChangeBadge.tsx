import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatPercent } from "@/lib/format";

interface ChangeBadgeProps {
  /** Raw ratio, e.g. 0.023 = +2.3% */
  value: number;
  variant?: "compact" | "full";
  className?: string;
}

export default function ChangeBadge({
  value,
  variant = "compact",
  className,
}: ChangeBadgeProps) {
  const isPositive = value > 0.0001;
  const isNegative = value < -0.0001;
  const isNeutral  = !isPositive && !isNegative;

  const colorClass = isPositive
    ? "text-success bg-success/10 border-success/20"
    : isNegative
    ? "text-danger  bg-danger/10  border-danger/20"
    : "text-muted   bg-border/40  border-border";

  const glowClass = isPositive
    ? "hover:shadow-[0_0_12px_-3px_rgba(0,255,136,0.5)]"
    : isNegative
    ? "hover:shadow-[0_0_12px_-3px_rgba(255,59,59,0.5)]"
    : "";

  const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
        "text-xs font-semibold font-mono tabular-nums",
        "transition-shadow duration-200",
        colorClass,
        glowClass,
        variant === "full" && "px-3 py-1 text-sm",
        className
      )}
      aria-label={`${isPositive ? "up" : isNegative ? "down" : "flat"} ${Math.abs(value * 100).toFixed(2)} percent`}
    >
      <Icon
        className={cn("shrink-0", variant === "compact" ? "size-3" : "size-4")}
        aria-hidden
      />
      {isNeutral ? "0.00%" : formatPercent(value)}
    </span>
  );
}
