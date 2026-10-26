/** Core domain types for StockMind frontend. */

export type Stock = {
  ticker: string;
  name: string;
  price: number;
  change: number;          // absolute price change
  changePercent: number;   // relative change (e.g. 0.023 = +2.3%)
  marketCap: number;
  volume: number;
  sector: string;
  logo?: string;           // emoji or URL
  high52w?: number;
  low52w?: number;
  peRatio?: number;
};

export type Candle = {
  time: string;   // ISO date string
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Prediction = {
  ticker: string;
  horizon: "1d" | "7d" | "30d";
  predictedChangePercent: number;  // e.g. 0.053 = +5.3%
  confidence: number;              // 0..1
  direction: "up" | "down" | "neutral";
  reasoning: string;
  generatedAt: string;             // ISO datetime
};

export type MarketOutlook = {
  sentiment: "bullish" | "bearish" | "neutral";
  confidence: number;   // 0..1
  summary: string;
  updatedAt: string;    // ISO datetime
};

export type NewsItem = {
  id: string;
  ticker: string;
  title: string;
  source: string;
  publishedAt: string;   // ISO datetime
  sentiment: "positive" | "negative" | "neutral";
  url?: string;
};

export type WatchlistItem = {
  ticker: string;
  addedAt: string;   // ISO datetime
};

/** Time range options for price charts. */
export type TimeRange = "1D" | "1W" | "1M" | "3M" | "1Y" | "ALL";

/** AI provider options (UI only, no backend logic). */
export type AiProvider = "ollama" | "nvidia";

/** App settings stored client-side. */
export type AppSettings = {
  theme: "dark" | "light" | "system";
  aiProvider: AiProvider;
  language: "de" | "en";
};
