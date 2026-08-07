"use client";

import { useMemo, useState } from "react";
import {
  ComposedChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { Candle, TimeRange } from "@/lib/types";
import { formatPrice, formatLargeNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PriceChartProps {
  candles: Candle[];
  ticker: string;
}

const RANGES: TimeRange[] = ["1D", "1W", "1M", "3M", "1Y", "ALL"];

const RANGE_DAYS: Record<TimeRange, number | null> = {
  "1D":  1,
  "1W":  5,
  "1M":  21,
  "3M":  63,
  "1Y":  null,   // show all if < 1Y
  "ALL": null,
};

function formatAxisDate(dateStr: string, range: TimeRange): string {
  const d = new Date(dateStr);
  if (range === "1D" || range === "1W")
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  if (range === "1M" || range === "3M")
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

interface OhlcvPayload {
  time:   string;
  open:   number;
  high:   number;
  low:    number;
  close:  number;
  volume: number;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { payload: OhlcvPayload }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const isUp = d.close >= d.open;

  return (
    <div className="glass rounded-lg px-3 py-2.5 text-xs space-y-1 min-w-[140px]">
      <p className="text-foreground-muted font-medium">{label}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        {(
          [
            ["O", d.open],
            ["H", d.high],
            ["L", d.low],
            ["C", d.close],
          ] as [string, number][]
        ).map(([key, val]) => (
          <span key={key} className={cn("font-mono", key === "C" && (isUp ? "text-success" : "text-danger"))}>
            <span className="text-foreground-muted mr-1">{key}</span>
            {val.toFixed(2)}
          </span>
        ))}
      </div>
      <p className="text-foreground-muted font-mono">
        Vol <span className="text-foreground">{formatLargeNumber(d.volume)}</span>
      </p>
    </div>
  );
}

export default function PriceChart({ candles, ticker }: PriceChartProps) {
  const [range, setRange] = useState<TimeRange>("1M");

  const data = useMemo(() => {
    const days = RANGE_DAYS[range];
    const slice = days ? candles.slice(-days) : candles;
    return slice.map((c) => ({ ...c, label: formatAxisDate(c.time, range) }));
  }, [candles, range]);

  const isUp = useMemo(() => {
    if (data.length < 2) return true;
    return data[data.length - 1].close >= data[0].close;
  }, [data]);

  const color = isUp ? "#00FF88" : "#FF3B3B";

  // Y-axis price domain with 3% padding
  const closes = data.map((d) => d.close);
  const priceMin = Math.min(...closes) * 0.97;
  const priceMax = Math.max(...closes) * 1.03;

  const volumes = data.map((d) => d.volume);
  const volMax = Math.max(...volumes) * 4; // volume bars in lower 25%

  return (
    <div className="space-y-3">
      {/* Range toggle */}
      <div className="flex items-center gap-1" role="group" aria-label="Time range">
        {RANGES.map((r) => (
          <button
            key={r}
            onClick={() => setRange(r)}
            className={cn(
              "px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150",
              range === r
                ? "bg-primary/15 text-primary"
                : "text-foreground-muted hover:text-foreground hover:bg-card"
            )}
            aria-pressed={range === r}
          >
            {r}
          </button>
        ))}
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`price-grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.2} />
              <stop offset="95%" stopColor={color} stopOpacity={0}   />
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

          {/* Price Y-axis (left) */}
          <YAxis
            yAxisId="price"
            domain={[priceMin, priceMax]}
            tick={{ fill: "#6B7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => formatPrice(v).replace("$", "")}
            width={56}
          />

          {/* Volume Y-axis (right, hidden) */}
          <YAxis
            yAxisId="volume"
            orientation="right"
            domain={[0, volMax]}
            hide
          />

          <Tooltip
            content={<CustomTooltip />}
            cursor={{ stroke: "rgba(255,255,255,0.1)", strokeWidth: 1 }}
          />

          {/* Volume bars */}
          <Bar
            yAxisId="volume"
            dataKey="volume"
            fill="rgba(107,114,128,0.25)"
            radius={[2, 2, 0, 0]}
            isAnimationActive={false}
          />

          {/* Price area */}
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke={color}
            strokeWidth={2}
            fill={`url(#price-grad-${ticker})`}
            dot={false}
            activeDot={{ r: 4, fill: color, stroke: "#0B0F1A", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
