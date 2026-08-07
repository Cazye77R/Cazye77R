import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WatchlistState {
  tickers: string[];
  add:    (ticker: string) => void;
  remove: (ticker: string) => void;
  toggle: (ticker: string) => void;
  has:    (ticker: string) => boolean;
  clear:  () => void;
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      tickers: ["AAPL", "MSFT", "NVDA"],

      add: (ticker) =>
        set((s) => ({
          tickers: s.tickers.includes(ticker)
            ? s.tickers
            : [...s.tickers, ticker],
        })),

      remove: (ticker) =>
        set((s) => ({ tickers: s.tickers.filter((t) => t !== ticker) })),

      toggle: (ticker) =>
        get().has(ticker) ? get().remove(ticker) : get().add(ticker),

      has: (ticker) => get().tickers.includes(ticker),

      clear: () => set({ tickers: [] }),
    }),
    { name: "stockmind-watchlist" }
  )
);
