"use client";

import { useEffect } from "react";
import { useWatchlistStore } from "@/store/watchlist-store";

/**
 * Triggers the one-time client-side load of the watchlist from
 * localStorage. The store is created with `skipHydration: true`, so this
 * runs after mount (not during the hydration pass) — see the comment in
 * store/watchlist-store.ts for why that avoids a hydration mismatch.
 */
export default function WatchlistHydrator() {
  useEffect(() => {
    useWatchlistStore.persist.rehydrate();
  }, []);

  return null;
}
