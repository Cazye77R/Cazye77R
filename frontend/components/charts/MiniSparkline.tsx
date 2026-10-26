"use client";

import { useMemo } from "react";
import { ResponsiveContainer, AreaChart, Area, Tooltip } from "recharts";
import type { Candle } from "@/lib/types";

interface MiniSparklineProps {
  candles: Candle[];
  /** Number of trailing candles to display. Default 30 */
  days?: number;
  /** Height in px. Default 60 */
  height?: number;
  /** Override auto-detected trend color */
  positive?: boolean;
}

export default function MiniSparkline({
  candles,
  days = 30,
  height = 60,
  positive,
}: MiniSparklineProps) {
  const data = useMemo(() => {
    const slice = candles.slice(-days);
    return slice.map((c) => ({ close: c.close }));
  }, [candles, days]);

  const isUp = useMemo(() => {
    if (positive !== undefined) return positive;
    if (data.length < 2) return true;
    return data[data.length - 1].close >= data[0].close;
  }, [data, positive]);

  const color = isUp ? "#00FF88" : "#FF3B3B";
  const gradientId = `spark-grad-${color.replace("#", "")}`;

  if (data.length === 0) return null;

  return (
    <div style={{ width: "100%", height }} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
              <stop offset="95%" stopColor={color} stopOpacity={0}    />
            </linearGradient>
          </defs>
          <Tooltip
            content={() => null}
            cursor={false}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${gradientId})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
