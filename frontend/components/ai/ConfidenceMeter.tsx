"use client";

import { cn } from "@/lib/utils";
import AnimatedNumber from "@/components/shared/AnimatedNumber";

interface ConfidenceMeterProps {
  /** 0..1 */
  value: number;
  label?: string;
  className?: string;
}

function confidenceColor(v: number): { bar: string; text: string } {
  if (v >= 0.7) return { bar: "bg-success", text: "text-success" };
  if (v >= 0.4) return { bar: "bg-accent",  text: "text-accent" };
  return           { bar: "bg-danger",  text: "text-danger" };
}

export default function ConfidenceMeter({
  value,
  label = "Konfidenz",
  className,
}: ConfidenceMeterProps) {
  const pct = Math.min(1, Math.max(0, value)) * 100;
  const { bar, text } = confidenceColor(value);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-foreground-muted">{label}</span>
        <AnimatedNumber
          value={pct}
          format="number"
          decimals={0}
          className={cn("text-sm font-semibold", text)}
        />
        <span className={cn("text-sm font-semibold", text)}>%</span>
      </div>

      {/* Track */}
      <div
        className="relative h-2 w-full overflow-hidden rounded-full bg-border"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${Math.round(pct)}%`}
      >
        {/* Fill */}
        <div
          className={cn("h-full rounded-full transition-all duration-700 ease-out", bar)}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Tier labels */}
      <div className="flex justify-between text-[10px] text-foreground-muted/60 select-none">
        <span>Niedrig</span>
        <span>Mittel</span>
        <span>Hoch</span>
      </div>
    </div>
  );
}
