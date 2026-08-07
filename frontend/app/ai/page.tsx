"use client";

import { useState } from "react";
import type { Prediction } from "@/lib/types";
import { STOCKS, getPrediction } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import { Button }       from "@/components/ui/button";
import { Sparkles }     from "lucide-react";
import AiThinking       from "@/components/ai/AiThinking";
import PredictionCard   from "@/components/ai/PredictionCard";

type Horizon = "1d" | "7d" | "30d";

const HORIZON_OPTS: { value: Horizon; label: string; desc: string }[] = [
  { value: "1d",  label: "1 Tag",   desc: "Kurzfristig" },
  { value: "7d",  label: "7 Tage",  desc: "Mittelfristig" },
  { value: "30d", label: "30 Tage", desc: "Langfristig" },
];

export default function AiPage() {
  const [ticker,  setTicker]  = useState("AAPL");
  const [horizon, setHorizon] = useState<Horizon>("7d");
  const [loading, setLoading] = useState(false);
  const [result,  setResult]  = useState<Prediction | null>(null);

  async function handlePredict() {
    setLoading(true);
    setResult(null);
    await new Promise((r) => setTimeout(r, 1500));
    setResult(getPrediction(ticker, horizon) ?? null);
    setLoading(false);
  }

  const selectedStock = STOCKS.find((s) => s.ticker === ticker)!;

  return (
    <div className="mx-auto max-w-md px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">AI Prediction</h1>
        <p className="text-sm text-foreground-muted mt-1">
          Wähle eine Aktie und einen Zeithorizont.
        </p>
      </div>

      {/* ── Stock selector ── */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-foreground-muted uppercase tracking-widest" htmlFor="stock-select">
          Aktie
        </label>
        <div className="relative">
          <select
            id="stock-select"
            value={ticker}
            onChange={(e) => { setTicker(e.target.value); setResult(null); }}
            className={cn(
              "w-full appearance-none rounded-xl border border-border bg-surface",
              "px-4 py-3 text-sm text-foreground",
              "focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30",
              "transition-colors duration-200 cursor-pointer"
            )}
            aria-label="Aktie wählen"
          >
            {STOCKS.map((s) => (
              <option key={s.ticker} value={s.ticker}>
                {s.logo} {s.ticker} – {s.name}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted">
            ▾
          </div>
        </div>

        {/* Selected stock info */}
        <div className="flex items-center gap-2 px-1">
          <span className="text-sm font-mono text-foreground">${selectedStock.price.toFixed(2)}</span>
          <span className={cn("text-xs font-mono", selectedStock.changePercent >= 0 ? "text-success" : "text-danger")}>
            {selectedStock.changePercent >= 0 ? "+" : ""}{(selectedStock.changePercent * 100).toFixed(2)}%
          </span>
          <span className="text-xs text-foreground-muted">{selectedStock.sector}</span>
        </div>
      </div>

      {/* ── Horizon selector ── */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-foreground-muted uppercase tracking-widest">
          Zeithorizont
        </p>
        <div className="grid grid-cols-3 gap-2" role="group" aria-label="Zeithorizont wählen">
          {HORIZON_OPTS.map(({ value, label, desc }) => (
            <button
              key={value}
              onClick={() => { setHorizon(value); setResult(null); }}
              aria-pressed={horizon === value}
              className={cn(
                "flex flex-col items-center gap-0.5 rounded-xl border py-3 px-2 transition-all duration-200",
                horizon === value
                  ? "border-primary/40 bg-primary/10 text-primary shadow-[0_0_16px_-4px_rgba(0,212,255,0.4)]"
                  : "border-border bg-surface text-foreground-muted hover:border-primary/20 hover:bg-card"
              )}
            >
              <span className="text-sm font-bold">{label}</span>
              <span className="text-[10px] opacity-70">{desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Predict button ── */}
      <Button
        onClick={handlePredict}
        disabled={loading}
        size="lg"
        className="w-full gap-2 text-base"
        aria-busy={loading}
      >
        <Sparkles className="size-5" aria-hidden />
        {loading ? "Analysiere…" : "Vorhersage starten"}
      </Button>

      {/* ── Loading animation ── */}
      {loading && (
        <div className="flex flex-col items-center gap-4 py-8">
          <AiThinking label="KI analysiert Marktdaten…" />
          <p className="text-xs text-foreground-muted text-center max-w-[200px]">
            Berechne Signale aus technischen Indikatoren und Sentiment-Daten…
          </p>
        </div>
      )}

      {/* ── Result ── */}
      {result && !loading && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-foreground-muted uppercase tracking-widest">
            Ergebnis
          </p>
          <PredictionCard prediction={result} />
        </div>
      )}
    </div>
  );
}
