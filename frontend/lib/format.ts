/**
 * Formatting utilities for prices, percentages, and large numbers.
 * All functions are pure and locale-aware (de-DE / en-US).
 */

const LOCALE = "en-US";

/** Format a price with currency symbol. e.g. 1234.56 → "$1,234.56" */
export function formatPrice(value: number, currency = "USD"): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Format a percentage with sign. e.g. 0.0345 → "+3.45%"
 * Pass raw ratio (0.035) not already-multiplied value.
 */
export function formatPercent(value: number, alreadyMultiplied = false): string {
  const pct = alreadyMultiplied ? value : value * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

/**
 * Format large market-cap / volume numbers with suffixes.
 * e.g. 1_230_000_000 → "1.23B",  450_000_000 → "450M"
 */
export function formatLargeNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (abs >= 1e9)  return `${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6)  return `${(value / 1e6).toFixed(2)}M`;
  if (abs >= 1e3)  return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

/** Format a plain number with commas. e.g. 1234567 → "1,234,567" */
export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** Format a date string to a short human-readable form. e.g. "2026-04-01" → "Apr 1, 2026" */
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(iso));
}

/** Format a datetime string to relative time. e.g. "2 hours ago" */
export function formatRelativeTime(iso: string): string {
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  const diffMs = new Date(iso).getTime() - Date.now();
  const diffMins = Math.round(diffMs / 60_000);
  const diffHours = Math.round(diffMs / 3_600_000);
  const diffDays = Math.round(diffMs / 86_400_000);

  if (Math.abs(diffMins) < 60)  return rtf.format(diffMins, "minute");
  if (Math.abs(diffHours) < 24) return rtf.format(diffHours, "hour");
  return rtf.format(diffDays, "day");
}
