"use client";

import dynamic from "next/dynamic";
import type { Stock, Candle, Prediction, NewsItem } from "@/lib/types";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { formatLargeNumber, formatPrice, formatRelativeTime } from "@/lib/format";
import PredictionCard   from "@/components/ai/PredictionCard";

const PriceChart = dynamic(
  () => import("@/components/charts/PriceChart"),
  {
    ssr: false,
    loading: () => (
      <div className="shimmer rounded" style={{ width: "100%", height: 280 }} />
    ),
  }
);

const PredictionOverlay = dynamic(
  () => import("@/components/charts/PredictionOverlay"),
  {
    ssr: false,
    loading: () => (
      <div className="shimmer rounded" style={{ width: "100%", height: 240 }} />
    ),
  }
);

interface StockDetailTabsProps {
  stock:      Stock;
  candles:    Candle[];
  prediction: Prediction;
  news:       NewsItem[];
}

const SENTIMENT_BADGE = {
  positive: "success",
  negative: "danger",
  neutral:  "muted",
} as const;

export default function StockDetailTabs({
  stock,
  candles,
  prediction,
  news,
}: StockDetailTabsProps) {
  return (
    <Tabs defaultValue="overview">
      <TabsList className="w-full">
        <TabsTrigger value="overview"   className="flex-1">Overview</TabsTrigger>
        <TabsTrigger value="prediction" className="flex-1">AI Signal</TabsTrigger>
        <TabsTrigger value="news"       className="flex-1">News</TabsTrigger>
      </TabsList>

      {/* ── Overview ── */}
      <TabsContent value="overview" className="space-y-5">
        {/* Price chart */}
        <div className="rounded-xl border border-border bg-card p-4">
          <PriceChart candles={candles} ticker={stock.ticker} />
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-3">
          {[
            ["Volumen",       formatLargeNumber(stock.volume)],
            ["Market Cap",    formatLargeNumber(stock.marketCap)],
            ["52w Hoch",      formatPrice(stock.high52w ?? stock.price * 1.1)],
            ["52w Tief",      formatPrice(stock.low52w  ?? stock.price * 0.8)],
            ["KGV",           stock.peRatio ? stock.peRatio.toFixed(1) : "–"],
            ["Sektor",        stock.sector],
          ].map(([label, value]) => (
            <div
              key={label}
              className="rounded-xl bg-surface border border-border p-3"
            >
              <p className="text-xs text-foreground-muted">{label}</p>
              <p className="mt-0.5 text-sm font-semibold text-foreground font-mono">{value}</p>
            </div>
          ))}
        </div>
      </TabsContent>

      {/* ── AI Signal ── */}
      <TabsContent value="prediction" className="space-y-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-foreground-muted mb-3">
            Kursverlauf + KI-Prognose (30 Tage)
          </p>
          <PredictionOverlay
            candles={candles}
            prediction={prediction}
            ticker={stock.ticker}
          />
        </div>
        <PredictionCard prediction={prediction} />
      </TabsContent>

      {/* ── News ── */}
      <TabsContent value="news" className="space-y-3">
        {news.length === 0 ? (
          <p className="text-center text-foreground-muted text-sm py-8">
            Keine Neuigkeiten verfügbar.
          </p>
        ) : (
          news.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-border bg-card p-4 space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-foreground leading-snug">
                  {item.title}
                </p>
                <Badge
                  variant={SENTIMENT_BADGE[item.sentiment]}
                  className="shrink-0 mt-0.5"
                >
                  {item.sentiment === "positive"
                    ? "Positiv"
                    : item.sentiment === "negative"
                    ? "Negativ"
                    : "Neutral"}
                </Badge>
              </div>
              <div className="flex items-center gap-2 text-xs text-foreground-muted">
                <span className="font-medium">{item.source}</span>
                <span>·</span>
                <span>{formatRelativeTime(item.publishedAt)}</span>
              </div>
            </div>
          ))
        )}
      </TabsContent>
    </Tabs>
  );
}
