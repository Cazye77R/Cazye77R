"use client";

import { useMemo } from "react";
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import type { Candle, Prediction } from "@/lib/types";
import { formatPrice, formatLargeNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PredictionOverlayProps {
  candles: Candle[];
  prediction: Prediction;
  ticker: string;
}

interface ChartPoint {
  label:           string;
  close?:          number;   // historical
  predClose?:      number;   // prediction line
  confUpper?:      number;   // confidence band top
  confLower?:      number;   // confidence band bottom
  isNow?:          boolean;
}

/** Add calendar days to a date string (skips weekends). */
function addTradingDays(startIso: string, n: number): string[] {
  const dates: string[] = [];
  const d = new Date(startIso);
  while (dates.length < n) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) {
      dates.push(d.toISOString().slice(0, 10));
    }
  }
  return dates;
}

function horizonToDays(h: "1d" | "7d" | "30d"): number {
  return h === "1d" ? 1 : h === "7d" ? 5 : 22;
}

function fmtLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day:   "numeric",
  });
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass rounded-lg px-3 py-2 text-xs space-y-1 min-w-[130px]">
      <p className="text-foreground-muted font-medium">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="font-mono" style={{ color: p.color }}>
          {p.name}: {formatPrice(p.value)}
        </p>
      ))}
    </div>
  );
}

export default function PredictionOverlay({
  candles,
  prediction,
  ticker,
}: PredictionOverlayProps) {
  const data = useMemo((): ChartPoint[] => {
    // Show last 30 historical candles
    const hist = candles.slice(-30);
    if (!hist.length) return [];

    const lastCandle = hist[hist.length - 1];
    const lastPrice  = lastCandle.close;
    const nowLabel   = fmtLabel(lastCandle.time);

    // Historical points
    const points: ChartPoint[] = hist.map((c) => ({
      label: fmtLabel(c.time),
      close: c.close,
    }));

    // Anchor: last historical price is also the start of prediction
    points[points.length - 1] = {
      ...points[points.length - 1],
      predClose:  lastPrice,
      confUpper:  lastPrice,
      confLower:  lastPrice,
      isNow:      true,
    };

    // Generate future prediction points
    const futureDays    = horizonToDays(prediction.horizon);
    const targetPrice   = lastPrice * (1 + prediction.predictedChangePercent);
    const uncertainty   = lastPrice * Math.abs(prediction.predictedChangePercent)
                          * (1 - prediction.confidence) * 1.5;
    const futureDates   = addTradingDays(lastCandle.time, futureDays);

    futureDates.forEach((date, i) => {
      const t        = (i + 1) / futureDays;  // 0 → 1
      const midPrice = lastPrice + (targetPrice - lastPrice) * t;
      // Band widens linearly with time
      const band     = uncertainty * t;

      points.push({
        label:     fmtLabel(date),
        predClose: +midPrice.toFixed(2),
        confUpper: +(midPrice + band).toFixed(2),
        confLower: +(midPrice - band).toFixed(2),
      });
    });

    return points;
  }, [candles, prediction]);

  const nowLabel = data.find((d) => d.isNow)?.label ?? "";

  const allPrices = data.flatMap((d) =>
    [d.close, d.confUpper, d.confLower].filter((v): v is number => v !== undefined)
  );
  const priceMin = Math.min(...allPrices) * 0.97;
  const priceMax = Math.max(...allPrices) * 1.03;

  const histColor    = "#00D4FF";
  const predColor    = "#6C63FF";
  const confColor    = "#6C63FF";

  const isUp = prediction.predictedChangePercent >= 0;

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-foreground-muted">
        <span className="flex items-center gap-1.5">
          <span className="block w-6 h-0.5 bg-primary rounded" />
          Historical
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="block w-6 h-0.5 rounded"
            style={{ background: predColor, borderTop: "2px dashed " + predColor }}
          />
          Prediction ({prediction.horizon})
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="block w-4 h-3 rounded"
            style={{ background: confColor, opacity: 0.15 }}
          />
          Confidence band
        </span>
        <span
          className={cn(
            "ml-auto font-semibold font-mono",
            isUp ? "text-success" : "text-danger"
          )}
        >
          {isUp ? "+" : ""}
          {(prediction.predictedChangePercent * 100).toFixed(2)}%
        </span>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`hist-grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={histColor} stopOpacity={0.18} />
              <stop offset="95%" stopColor={histColor} stopOpacity={0}    />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(42,51,68,0.6)"
            vertical={false}
          />

          <XAxis
            dataKey="label"
            tick={{ fill: "#6B7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            domain={[priceMin, priceMax]}
            tick={{ fill: "#6B7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) =>
              formatPrice(v).replace("$", "").replace(",", "")
            }
            width={52}
          />

          <Tooltip content={<CustomTooltip />} />

          {/* "Now" vertical reference line */}
          <ReferenceLine
            x={nowLabel}
            stroke="rgba(255,255,255,0.2)"
            strokeDasharray="4 4"
            label={{
              value: "Now",
              position: "insideTopRight",
              fill: "#6B7280",
              fontSize: 10,
            }}
          />

          {/* Confidence band (area between upper and lower) */}
          <Area
            type="monotone"
            dataKey="confUpper"
            stroke="none"
            fill={confColor}
            fillOpacity={0.1}
            dot={false}
            legendType="none"
            isAnimationActive={false}
            name="Upper bound"
          />
          <Area
            type="monotone"
            dataKey="confLower"
            stroke="none"
            fill={confColor}
            fillOpacity={0}   // transparent – just defines the bottom of the band
            dot={false}
            legendType="none"
            isAnimationActive={false}
            name="Lower bound"
          />

          {/* Historical price area */}
          <Area
            type="monotone"
            dataKey="close"
            stroke={histColor}
            strokeWidth={2}
            fill={`url(#hist-grad-${ticker})`}
            dot={false}
            activeDot={{ r: 4, fill: histColor, stroke: "#0B0F1A", strokeWidth: 2 }}
            isAnimationActive={false}
            name="Close"
          />

          {/* Prediction line (dashed) */}
          <Line
            type="monotone"
            dataKey="predClose"
            stroke={predColor}
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={{ r: 4, fill: predColor, stroke: "#0B0F1A", strokeWidth: 2 }}
            isAnimationActive={false}
            name="Predicted"
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Confidence note */}
      <p className="text-xs text-foreground-muted text-right">
        Model confidence:{" "}
        <span
          className={cn(
            "font-semibold",
            prediction.confidence >= 0.7
              ? "text-success"
              : prediction.confidence >= 0.4
              ? "text-accent"
              : "text-danger"
          )}
        >
          {Math.round(prediction.confidence * 100)}%
        </span>
      </p>
    </div>
  );
}
