/**
 * Data-access layer for stocks, market outlook, and news.
 *
 * Every consumer in the app should import from here, not from
 * `lib/mock-data` directly. Today these are synchronous passthroughs to
 * the in-memory mock catalogue; swapping in a real backend later means
 * changing the implementations in THIS file (e.g. to `async` functions
 * backed by `fetch(...)`), instead of touching every page/component that
 * currently reads `lib/mock-data` directly.
 *
 * Note: this keeps the same synchronous signatures `lib/mock-data`
 * already had — it does not pre-emptively convert the app to async data
 * fetching, since that would also require every consumer to handle
 * loading/error states they don't have today. That's a follow-up for
 * whenever a real backend actually exists, not something to guess at now.
 */
import {
  STOCKS,
  TRENDING_STOCKS,
  MARKET_OUTLOOK,
  NEWS,
  getStock as _getStock,
  getCandles as _getCandles,
  getPrediction as _getPrediction,
} from "@/lib/mock-data";
import type { Stock, Candle, Prediction, MarketOutlook, NewsItem } from "@/lib/types";

export function getAllStocks(): Stock[] {
  return STOCKS;
}

export function getTrendingStocks(): Stock[] {
  return TRENDING_STOCKS;
}

export function getMarketOutlook(): MarketOutlook {
  return MARKET_OUTLOOK;
}

export function getStock(ticker: string): Stock | undefined {
  return _getStock(ticker);
}

export function getCandles(ticker: string, days?: number): Candle[] {
  return _getCandles(ticker, days);
}

export function getPrediction(
  ticker: string,
  horizon: "1d" | "7d" | "30d"
): Prediction | undefined {
  return _getPrediction(ticker, horizon);
}

export function getNews(ticker: string): NewsItem[] {
  return NEWS[ticker] ?? [];
}
