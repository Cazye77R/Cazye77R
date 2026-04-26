/**
 * Mock data for StockMind frontend.
 * All values are pure TypeScript constants – no async, no API calls.
 * Prices are plausible for Q1 2026. Candle history is generated via a
 * seeded deterministic random walk so the data is stable across reloads.
 */

import type { Stock, Candle, Prediction, MarketOutlook, NewsItem } from "./types";

// ─── Seeded PRNG (mulberry32) ───────────────────────────────────────────────
function seededRng(seed: number) {
  let s = seed;
  return () => {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Generate 90-day OHLCV candle history for a ticker
function generateCandles(ticker: string, startPrice: number, drift = 0.0003): Candle[] {
  const rng = seededRng(ticker.split("").reduce((a, c) => a + c.charCodeAt(0), 0));
  const candles: Candle[] = [];
  let price = startPrice;

  const today = new Date("2026-04-26");
  for (let i = 89; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    // Skip weekends
    if (d.getDay() === 0 || d.getDay() === 6) continue;

    const vol   = (rng() - 0.48) * 0.025 + drift;
    const open  = price;
    const close = open * (1 + vol);
    const high  = Math.max(open, close) * (1 + rng() * 0.008);
    const low   = Math.min(open, close) * (1 - rng() * 0.008);
    const volume = Math.round((rng() * 0.8 + 0.4) * 50_000_000);

    candles.push({
      time:   d.toISOString().slice(0, 10),
      open:   +open.toFixed(2),
      high:   +high.toFixed(2),
      low:    +low.toFixed(2),
      close:  +close.toFixed(2),
      volume,
    });
    price = close;
  }
  return candles;
}

// ─── Stock catalogue ────────────────────────────────────────────────────────
const RAW_STOCKS: {
  ticker: string; name: string; price: number; change: number;
  changePercent: number; marketCap: number; volume: number;
  sector: string; logo: string; high52w: number; low52w: number;
  peRatio: number; drift: number;
}[] = [
  { ticker: "AAPL",   name: "Apple Inc.",               price: 312.45, change:  4.82, changePercent:  0.0157, marketCap: 4_780_000_000_000, volume: 62_400_000, sector: "Technology",   logo: "🍎", high52w: 328.90, low52w: 234.10, peRatio: 33.2, drift:  0.0004 },
  { ticker: "MSFT",   name: "Microsoft Corp.",           price: 487.20, change:  6.15, changePercent:  0.0128, marketCap: 3_620_000_000_000, volume: 24_100_000, sector: "Technology",   logo: "🪟", high52w: 512.40, low52w: 370.20, peRatio: 38.7, drift:  0.0005 },
  { ticker: "NVDA",   name: "NVIDIA Corp.",              price: 194.60, change: -3.40, changePercent: -0.0172, marketCap: 4_760_000_000_000, volume: 218_000_000, sector: "Technology",  logo: "🟢", high52w: 231.80, low52w: 138.40, peRatio: 52.1, drift:  0.0008 },
  { ticker: "TSLA",   name: "Tesla Inc.",                price: 378.90, change: -8.60, changePercent: -0.0222, marketCap: 1_210_000_000_000, volume: 89_300_000, sector: "Automotive",   logo: "⚡", high52w: 488.50, low52w: 214.70, peRatio: 98.4, drift: -0.0002 },
  { ticker: "SAP.DE", name: "SAP SE",                   price: 254.30, change:  2.10, changePercent:  0.0083, marketCap:  312_000_000_000, volume:  4_200_000, sector: "Technology",   logo: "🔵", high52w: 268.90, low52w: 192.40, peRatio: 41.2, drift:  0.0003 },
  { ticker: "ASML",   name: "ASML Holding N.V.",        price: 921.40, change: 14.20, changePercent:  0.0156, marketCap:  362_000_000_000, volume:  1_800_000, sector: "Semiconductors",logo: "🔬", high52w: 978.60, low52w: 647.30, peRatio: 46.8, drift:  0.0006 },
  { ticker: "AMZN",   name: "Amazon.com Inc.",           price: 268.75, change:  3.45, changePercent:  0.0130, marketCap: 2_820_000_000_000, volume: 48_600_000, sector: "E-Commerce",   logo: "📦", high52w: 284.20, low52w: 198.70, peRatio: 44.5, drift:  0.0004 },
  { ticker: "GOOGL",  name: "Alphabet Inc.",             price: 236.80, change:  1.95, changePercent:  0.0083, marketCap: 2_930_000_000_000, volume: 31_200_000, sector: "Technology",   logo: "🔍", high52w: 251.40, low52w: 182.60, peRatio: 28.3, drift:  0.0003 },
  { ticker: "META",   name: "Meta Platforms Inc.",       price: 718.40, change: 12.80, changePercent:  0.0181, marketCap: 1_820_000_000_000, volume: 19_700_000, sector: "Social Media", logo: "👤", high52w: 756.20, low52w: 512.30, peRatio: 31.7, drift:  0.0005 },
  { ticker: "AMD",    name: "Advanced Micro Devices",   price: 162.30, change: -2.15, changePercent: -0.0131, marketCap:  263_000_000_000, volume: 54_800_000, sector: "Semiconductors",logo: "🔴", high52w: 198.70, low52w: 124.60, peRatio: 38.9, drift:  0.0002 },
  { ticker: "COIN",   name: "Coinbase Global Inc.",     price: 298.60, change: 11.40, changePercent:  0.0397, marketCap:   76_000_000_000, volume: 12_300_000, sector: "Fintech",       logo: "₿",  high52w: 384.20, low52w: 148.90, peRatio: 22.1, drift:  0.0009 },
  { ticker: "PLTR",   name: "Palantir Technologies",    price: 96.40,  change:  2.85, changePercent:  0.0304, marketCap:  208_000_000_000, volume: 68_500_000, sector: "AI/Defense",    logo: "🛡️", high52w: 124.80, low52w: 54.30,  peRatio: 187.4, drift: 0.0007 },
];

// ─── Stocks (plain objects, no candles here for perf) ───────────────────────
export const STOCKS: Stock[] = RAW_STOCKS.map(({ drift: _drift, ...s }) => s);

// ─── Candle histories ────────────────────────────────────────────────────────
export const CANDLES: Record<string, Candle[]> = Object.fromEntries(
  RAW_STOCKS.map(({ ticker, price, drift }) => [
    ticker,
    generateCandles(ticker, price * 0.88, drift),
  ])
);

// ─── Predictions ─────────────────────────────────────────────────────────────
const REASONINGS: Record<string, string> = {
  AAPL:   "Strong iPhone 17 Pro cycle demand and continued Services revenue growth suggest sustained momentum. RSI sits at 58, indicating room before overbought territory. MACD histogram turned positive three sessions ago.",
  MSFT:   "Azure cloud growth reaccelerating at 31% YoY driven by Copilot enterprise adoption. Valuation premium justified by AI monetisation visibility. Near-term resistance at $495 – watch for breakout.",
  NVDA:   "Blackwell GPU supply constraints easing in H2. Forward P/E of 32× appears compressed vs. peers given 80%+ data-center margin. Short-term profit-taking pressure after recent run-up.",
  TSLA:   "Declining EV market share in Europe (-4pp YoY) and intensifying Chinese competition weigh on margins. FSD v13 regulatory approval timeline remains uncertain. Sentiment oversold short-term.",
  "SAP.DE": "RISE with SAP cloud transition progressing ahead of schedule. 92% of revenue now recurring. Solid FCF generation at €3.8B/quarter. Defensive quality compounder.",
  ASML:   "EUV order backlog of €40B+ provides multi-year visibility. China sales restrictions create near-term drag but Korea/Taiwan orders compensate. Technical breakout above €900 confirms bullish trend.",
  AMZN:   "AWS quarterly revenue surpassed $40B for first time. Advertising business growing at 19% YoY. Logistics profitability inflecting positively. Core e-commerce margin expansion ongoing.",
  GOOGL:  "Gemini Ultra integration into search generates incremental revenue per query. YouTube Shorts monetisation reaching parity with long-form. Strong balance sheet with $110B net cash.",
  META:   "AI-driven ad targeting efficiency gains producing measurable ROAS improvement for advertisers. WhatsApp monetisation only at ~5% of potential. Reality Labs losses narrowing QoQ.",
  AMD:    "MI300X GPU demand robust but competing against NVDA's dominant CUDA ecosystem. PC segment recovering. Q2 data-center guidance in-line – no upside catalyst imminent.",
  COIN:   "Bitcoin above $100K correlated with elevated trading volumes and custody fee uplift. Regulatory clarity in US (SEC settlement) removes key overhang. High-beta crypto proxy.",
  PLTR:   "US Government AIP deals accelerating; commercial ARR growing 55% YoY. Valuation remains stretched at 47× revenue – priced for perfection. Insider selling pace worth monitoring.",
};

function makePrediction(stock: Stock, horizon: "1d" | "7d" | "30d"): Prediction {
  const rng = seededRng(stock.ticker.charCodeAt(0) * 7 + horizon.length * 13);
  const base = stock.changePercent;
  const multiplier = horizon === "1d" ? 1 : horizon === "7d" ? 2.8 : 6.5;
  const rawChange = base * multiplier + (rng() - 0.45) * 0.04;
  const confidence = Math.min(0.92, Math.max(0.38, 0.62 + (rng() - 0.5) * 0.4));
  const direction = rawChange > 0.005 ? "up" : rawChange < -0.005 ? "down" : "neutral";

  return {
    ticker:                  stock.ticker,
    horizon,
    predictedChangePercent:  +rawChange.toFixed(4),
    confidence:              +confidence.toFixed(2),
    direction,
    reasoning:               REASONINGS[stock.ticker] ?? "Technical and fundamental indicators point to near-term stability.",
    generatedAt:             "2026-04-26T08:00:00Z",
  };
}

export const PREDICTIONS: Record<string, Prediction[]> = Object.fromEntries(
  STOCKS.map((s) => [
    s.ticker,
    (["1d", "7d", "30d"] as const).map((h) => makePrediction(s, h)),
  ])
);

// ─── Trending stocks (top 5 by |changePercent|) ──────────────────────────────
export const TRENDING_STOCKS: Stock[] = [...STOCKS]
  .sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent))
  .slice(0, 5);

// ─── Global market outlook ───────────────────────────────────────────────────
export const MARKET_OUTLOOK: MarketOutlook = {
  sentiment:  "bullish",
  confidence: 0.71,
  summary:
    "Risk-on environment driven by Fed pivot expectations and strong Q1 earnings. AI infrastructure spending remains a secular tailwind. Watch for CPI release Thursday – hotter-than-expected print could trigger short-term volatility.",
  updatedAt: "2026-04-26T07:45:00Z",
};

// ─── News (3 per stock) ───────────────────────────────────────────────────────
const NEWS_TEMPLATES: Pick<NewsItem, "title" | "source" | "sentiment">[][] = [
  // AAPL
  [
    { title: "Apple's Vision Pro 2 Expected to Debut at WWDC with Thinner Form Factor", source: "Bloomberg", sentiment: "positive" },
    { title: "Services Revenue Hits Record $26B in Q2 Driven by App Store and iCloud+", source: "Reuters",   sentiment: "positive" },
    { title: "EU Probes Apple Intelligence Data Handling Under New AI Act Framework",   source: "FT",        sentiment: "negative" },
  ],
  // MSFT
  [
    { title: "Microsoft Copilot Reaches 500M Monthly Active Users Across Enterprise Suite", source: "WSJ",       sentiment: "positive" },
    { title: "Azure OpenAI Service Expands to 12 New Regions Amid Surging Demand",          source: "TechCrunch", sentiment: "positive" },
    { title: "Microsoft Faces Antitrust Scrutiny Over Teams Bundling in European Markets",   source: "FT",         sentiment: "negative" },
  ],
  // NVDA
  [
    { title: "NVIDIA Blackwell B200 GPUs Begin Volume Shipments to Hyperscalers",          source: "Reuters",    sentiment: "positive" },
    { title: "NVDA Q1 Data Center Revenue Beats at $26.1B; Gross Margin Hits 78.2%",      source: "Bloomberg",  sentiment: "positive" },
    { title: "US Tightens AI Chip Export Controls to Additional Southeast Asian Nations",  source: "FT",         sentiment: "negative" },
  ],
  // TSLA
  [
    { title: "Tesla Cuts Model Y Prices 4% in China Amid Intensifying Competition from BYD", source: "Reuters",  sentiment: "negative" },
    { title: "Cybercab Autonomous Taxi Service Soft Launch in Austin Draws Mixed Reviews",   source: "Bloomberg", sentiment: "neutral"  },
    { title: "FSD v13.2 Rollout Paused After Edge-Case Collision Reports in Nevada",         source: "WSJ",       sentiment: "negative" },
  ],
  // SAP.DE
  [
    { title: "SAP Cloud Revenue Surpasses €5B Quarter for the First Time in Company History", source: "Handelsblatt", sentiment: "positive" },
    { title: "SAP Acquires AI Workflow Startup Celonis Integration Layer for €1.2B",           source: "FT",           sentiment: "positive" },
    { title: "German Works Council Raises Concerns Over SAP AI-Driven Headcount Reduction",   source: "Reuters",      sentiment: "negative" },
  ],
  // ASML
  [
    { title: "ASML Books Record €9.1B in Orders in Q1 as Taiwan and Korea Rush for EUV Capacity", source: "Bloomberg",    sentiment: "positive" },
    { title: "High-NA EUV Adoption Accelerating: Intel and TSMC Confirm Multi-Tool Orders",        source: "Reuters",      sentiment: "positive" },
    { title: "Dutch Government Extends China Export Restrictions to Older DUV Systems",            source: "NRC Handelsblad",sentiment:"negative"},
  ],
  // AMZN
  [
    { title: "AWS Quarterly Revenue Tops $40B Milestone Driven by GenAI Workloads",         source: "CNBC",       sentiment: "positive" },
    { title: "Amazon Advertising Grows 19% YoY – Now Larger Than YouTube by Revenue",       source: "Bloomberg",  sentiment: "positive" },
    { title: "FTC Opens Investigation into Amazon Prime Cancellation Friction Practices",    source: "WSJ",        sentiment: "negative" },
  ],
  // GOOGL
  [
    { title: "Google Search Revenue Resilient Despite AI Competition; Gemini Integration Shows 8% Query Growth", source: "Bloomberg", sentiment: "positive" },
    { title: "Waymo Driverless Ride-Hailing Expands to 10 New US Cities with No Safety Driver",                  source: "TechCrunch",sentiment: "positive" },
    { title: "DOJ Pushes for Chrome Sale as Google Remedy Talks Stall",                                          source: "FT",        sentiment: "negative" },
  ],
  // META
  [
    { title: "Meta AI Assistant Reaches 1B Monthly Active Users Across WhatsApp and Messenger", source: "Reuters",  sentiment: "positive" },
    { title: "Ray-Ban Meta Glasses Gen 3 Sells Out Within 48 Hours of Global Launch",           source: "Bloomberg", sentiment: "positive" },
    { title: "Meta Faces €1.3B GDPR Fine in Ireland Over Cross-Context Data Processing",        source: "FT",        sentiment: "negative" },
  ],
  // AMD
  [
    { title: "AMD MI300X GPU Deployed at Microsoft Azure for Frontier AI Inference Workloads", source: "Reuters",    sentiment: "positive" },
    { title: "AMD PC Processor Market Share Reaches 28% – Highest Since 2006",                 source: "TechCrunch", sentiment: "positive" },
    { title: "Q1 Data Center Revenue Guidance Misses by 4%; CUDA Ecosystem Lock-in Cited",     source: "Bloomberg",  sentiment: "negative" },
  ],
  // COIN
  [
    { title: "Coinbase Custody Assets Surpass $300B as Institutional Bitcoin ETF Demand Surges", source: "Reuters",   sentiment: "positive" },
    { title: "SEC Drops Remaining Claims Against Coinbase After Historic Settlement",             source: "Bloomberg",  sentiment: "positive" },
    { title: "Base L2 Network Congestion Causes 6-Hour Outage; $2.4M in Fees Refunded",         source: "CoinDesk",   sentiment: "negative" },
  ],
  // PLTR
  [
    { title: "Palantir AIP Wins $900M US Army Logistics AI Contract",                            source: "DefenseNews", sentiment: "positive" },
    { title: "Commercial ARR Grows 55% YoY; US Commercial Segment Crosses $1B Annual Run Rate", source: "Reuters",     sentiment: "positive" },
    { title: "Palantir Insider Selling Accelerates; CEO Karp Offloads $180M in Shares via 10b5", source: "Bloomberg",  sentiment: "negative" },
  ],
];

export const NEWS: Record<string, NewsItem[]> = Object.fromEntries(
  STOCKS.map((s, idx) => [
    s.ticker,
    (NEWS_TEMPLATES[idx] ?? []).map((n, i) => ({
      ...n,
      id:          `${s.ticker}-news-${i}`,
      ticker:      s.ticker,
      publishedAt: new Date(Date.now() - (i + 1) * 3_600_000 * (i + 2)).toISOString(),
    })),
  ])
);

// ─── Helper: lookup ──────────────────────────────────────────────────────────
export function getStock(ticker: string): Stock | undefined {
  return STOCKS.find((s) => s.ticker === ticker);
}

export function getCandles(ticker: string, days?: number): Candle[] {
  const all = CANDLES[ticker] ?? [];
  return days ? all.slice(-days) : all;
}

export function getPrediction(ticker: string, horizon: "1d" | "7d" | "30d"): Prediction | undefined {
  return PREDICTIONS[ticker]?.find((p) => p.horizon === horizon);
}
