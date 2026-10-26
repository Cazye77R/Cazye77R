import type { Prediction } from "@/lib/types";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import AnimatedNumber  from "@/components/shared/AnimatedNumber";
import ConfidenceMeter from "@/components/ai/ConfidenceMeter";

interface PredictionCardProps {
  prediction: Prediction;
  /** Show the full reasoning block. Default true */
  showReasoning?: boolean;
}

const HORIZON_LABELS = { "1d": "1 Tag", "7d": "7 Tage", "30d": "30 Tage" } as const;

export default function PredictionCard({
  prediction,
  showReasoning = true,
}: PredictionCardProps) {
  const isUp   = prediction.direction === "up";
  const isDown = prediction.direction === "down";
  const pct    = prediction.predictedChangePercent * 100;

  const color  = isUp ? "text-success" : isDown ? "text-danger" : "text-accent";
  const bg     = isUp ? "bg-success/10" : isDown ? "bg-danger/10" : "bg-accent/10";
  const border = isUp ? "border-success/20" : isDown ? "border-danger/20" : "border-accent/20";
  const glow   = isUp
    ? "shadow-[0_0_30px_-8px_rgba(0,255,136,0.35)]"
    : isDown
    ? "shadow-[0_0_30px_-8px_rgba(255,59,59,0.35)]"
    : "shadow-[0_0_30px_-8px_rgba(108,99,255,0.35)]";

  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

  return (
    <div
      className={cn(
        "glass rounded-2xl border p-5 space-y-5",
        border,
        glow
      )}
    >
      {/* Header: ticker + horizon */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-foreground-muted">AI Signal · {HORIZON_LABELS[prediction.horizon]}</p>
          <p className="text-lg font-bold text-foreground">{prediction.ticker}</p>
        </div>
        <span
          className={cn(
            "flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-semibold border",
            bg,
            border,
            color
          )}
        >
          <Icon className="size-4" aria-hidden />
          {isUp ? "KAUFEN" : isDown ? "VERKAUFEN" : "HALTEN"}
        </span>
      </div>

      {/* Predicted change – large animated number */}
      <div className="flex items-end gap-3">
        <AnimatedNumber
          value={Math.abs(pct)}
          format="number"
          decimals={2}
          className={cn("text-4xl font-bold", color)}
        />
        <span className={cn("text-2xl font-bold mb-0.5", color)}>
          %{isUp ? " ↑" : isDown ? " ↓" : ""}
        </span>
        <span className="text-sm text-foreground-muted mb-1">
          vorhergesagt ({prediction.horizon})
        </span>
      </div>

      {/* Confidence meter */}
      <ConfidenceMeter value={prediction.confidence} />

      {/* Reasoning */}
      {showReasoning && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-foreground-muted uppercase tracking-widest">
            Begründung
          </p>
          <p className="text-sm text-foreground leading-relaxed">
            {prediction.reasoning}
          </p>
        </div>
      )}

      {/* Generated at */}
      <p className="text-xs text-foreground-muted border-t border-border pt-3">
        Generiert am {formatDate(prediction.generatedAt)}
      </p>
    </div>
  );
}
