import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WatchlistState {
  tickers: string[];
  /** True once the real persisted value has loaded (see WatchlistHydrator). */
  hasHydrated: boolean;
  add:    (ticker: string) => void;
  remove: (ticker: string) => void;
  toggle: (ticker: string) => void;
  has:    (ticker: string) => boolean;
  clear:  () => void;
  _setHasHydrated: (hydrated: boolean) => void;
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      tickers: ["AAPL", "MSFT", "NVDA"],
      hasHydrated: false,

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

      _setHasHydrated: (hydrated) => set({ hasHydrated: hydrated }),
    }),
    {
      name: "stockmind-watchlist",
      // The server always renders the default `tickers` above. Zustand's
      // normal persist behavior rehydrates from localStorage synchronously
      // during store creation, which on the client happens BEFORE the
      // first paint — producing a different first render than the server
      // HTML (React hydration mismatch + visible flicker for any user
      // with a saved watchlist). skipHydration defers that load; an
      // explicit `.persist.rehydrate()` call after mount (see
      // components/layout/WatchlistHydrator.tsx) then loads the real
      // value as an ordinary client-side state update, which is not a
      // hydration boundary and triggers no mismatch.
      skipHydration: true,
      onRehydrateStorage: () => (state) => {
        state?._setHasHydrated(true);
      },
    }
  )
);
