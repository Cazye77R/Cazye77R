import type { Metadata } from "next";
import { getAllStocks, getTrendingStocks, getMarketOutlook } from "@/lib/api/stocks";
import MarketOutlookCard from "@/components/ai/MarketOutlookCard";
import StockCard         from "@/components/stock/StockCard";
import WatchlistPreview  from "@/components/home/WatchlistPreview";
import TopMovers         from "@/components/home/TopMovers";

export const metadata: Metadata = { title: "Dashboard" };

export default function HomePage() {
  const stocks   = getAllStocks();
  const trending = getTrendingStocks();
  const outlook  = getMarketOutlook();

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 space-y-8">

      {/* ── Market Outlook hero ── */}
      <section aria-labelledby="outlook-heading">
        <h2
          id="outlook-heading"
          className="text-xs font-semibold text-foreground-muted uppercase tracking-widest mb-3"
        >
          Marktlage
        </h2>
        <MarketOutlookCard outlook={outlook} />
      </section>

      {/* ── Watchlist preview ── */}
      <section aria-labelledby="watchlist-heading">
        <h2
          id="watchlist-heading"
          className="text-xs font-semibold text-foreground-muted uppercase tracking-widest mb-3"
        >
          Deine Watchlist
        </h2>
        <WatchlistPreview />
      </section>

      {/* ── Trending ── */}
      <section aria-labelledby="trending-heading">
        <h2
          id="trending-heading"
          className="text-xs font-semibold text-foreground-muted uppercase tracking-widest mb-3"
        >
          Trending Now
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {trending.slice(0, 4).map((s) => (
            <StockCard key={s.ticker} stock={s} variant="trending" />
          ))}
        </div>
      </section>

      {/* ── Top Movers ── */}
      <section aria-labelledby="movers-heading">
        <h2
          id="movers-heading"
          className="text-xs font-semibold text-foreground-muted uppercase tracking-widest mb-3"
        >
          Top Movers
        </h2>
        <TopMovers stocks={stocks} />
      </section>

    </div>
  );
}
