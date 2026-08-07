import type { Metadata } from "next";
import { notFound }   from "next/navigation";
import { getStock, getCandles, getPrediction, NEWS } from "@/lib/mock-data";
import { formatPrice } from "@/lib/format";
import ChangeBadge     from "@/components/shared/ChangeBadge";
import WatchlistToggle from "@/components/stock/WatchlistToggle";
import StockDetailTabs from "@/components/stock/StockDetailTabs";

// In Next.js 16 params is always a Promise
export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const stock = getStock(ticker.toUpperCase());
  return {
    title: stock ? `${stock.ticker} – ${stock.name}` : ticker.toUpperCase(),
  };
}

export default async function StockPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: rawTicker } = await params;
  const ticker = rawTicker.toUpperCase();

  const stock      = getStock(ticker);
  if (!stock) notFound();

  const candles    = getCandles(ticker);
  const prediction = getPrediction(ticker, "30d")!;
  const news       = NEWS[ticker] ?? [];

  const isUp = stock.changePercent >= 0;

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 space-y-6">

      {/* ── Stock header ── */}
      <div className="flex items-start gap-4">
        {/* Logo */}
        <span className="text-4xl mt-1 shrink-0" aria-hidden>
          {stock.logo ?? "📈"}
        </span>

        {/* Name + price */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                {stock.ticker}
              </h1>
              <p className="text-sm text-foreground-muted truncate">{stock.name}</p>
            </div>
            <WatchlistToggle ticker={ticker} />
          </div>

          {/* Price row */}
          <div className="mt-3 flex items-end gap-3">
            <span
              className={`text-3xl font-mono font-bold ${isUp ? "text-success" : "text-danger"}`}
            >
              {formatPrice(stock.price)}
            </span>
            <div className="mb-0.5">
              <ChangeBadge value={stock.changePercent} variant="full" />
            </div>
          </div>

          {/* Absolute change */}
          <p className="mt-1 text-sm font-mono text-foreground-muted">
            {isUp ? "+" : ""}
            {formatPrice(stock.change)} heute
          </p>
        </div>
      </div>

      {/* ── Tabs: Overview / AI Signal / News ── */}
      <StockDetailTabs
        stock={stock}
        candles={candles}
        prediction={prediction}
        news={news}
      />

    </div>
  );
}
