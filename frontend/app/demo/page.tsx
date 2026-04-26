/**
 * Milestone 2 & 4 – Component showcase.
 * Visible at /demo during development only.
 */
import { Separator }    from "@/components/ui/separator";
import { Badge }        from "@/components/ui/badge";
import AnimatedNumber   from "@/components/shared/AnimatedNumber";
import ChangeBadge      from "@/components/shared/ChangeBadge";
import GlowCard         from "@/components/shared/GlowCard";
import AiThinking       from "@/components/ai/AiThinking";
import ConfidenceMeter  from "@/components/ai/ConfidenceMeter";
import StockCard        from "@/components/stock/StockCard";
import StockList        from "@/components/stock/StockList";
import PriceChart       from "@/components/charts/PriceChart";
import PredictionOverlay from "@/components/charts/PredictionOverlay";
import {
  STOCKS,
  MARKET_OUTLOOK,
  TRENDING_STOCKS,
  getCandles,
  getPrediction,
} from "@/lib/mock-data";

export default function DemoPage() {
  const aapl       = STOCKS.find((s) => s.ticker === "AAPL")!;
  const aaplCandles = getCandles("AAPL");
  const aaplPred30  = getPrediction("AAPL", "30d")!;

  return (
    <main className="min-h-screen p-6 space-y-12 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
        Component Demo (M2 + M4)
      </h1>

      {/* ── M2: AnimatedNumber ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">AnimatedNumber</h2>
        <div className="flex flex-wrap gap-6 items-end">
          <div>
            <p className="text-xs text-muted mb-1">currency</p>
            <AnimatedNumber value={aapl.price} format="currency" className="text-2xl text-foreground" />
          </div>
          <div>
            <p className="text-xs text-muted mb-1">percent</p>
            <AnimatedNumber value={aapl.changePercent * 100} format="percent" className="text-xl text-success" />
          </div>
          <div>
            <p className="text-xs text-muted mb-1">compact</p>
            <AnimatedNumber value={aapl.marketCap} format="compact" className="text-xl text-foreground" />
          </div>
        </div>
      </section>

      <Separator />

      {/* ── M2: ChangeBadge ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">ChangeBadge</h2>
        <div className="flex flex-wrap gap-3 items-center">
          <ChangeBadge value={0.0234}  variant="compact" />
          <ChangeBadge value={-0.0318} variant="compact" />
          <ChangeBadge value={0}       variant="compact" />
          <ChangeBadge value={0.0181}  variant="full" />
          <ChangeBadge value={-0.0222} variant="full" />
        </div>
      </section>

      <Separator />

      {/* ── M2: GlowCard ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">GlowCard (hover)</h2>
        <div className="grid grid-cols-2 gap-3">
          {(["primary", "accent", "success", "danger"] as const).map((glow) => (
            <GlowCard key={glow} glow={glow} className="p-4">
              <p className="text-xs text-foreground-muted">glow=&quot;{glow}&quot;</p>
              <p className="text-foreground font-semibold mt-1 capitalize">{glow}</p>
            </GlowCard>
          ))}
        </div>
      </section>

      <Separator />

      {/* ── M2: AiThinking + ConfidenceMeter ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">AI Components</h2>
        <GlowCard className="p-4 flex items-center justify-center" glow="accent">
          <AiThinking label="Modell lädt Vorhersage…" />
        </GlowCard>
        <GlowCard className="p-5 space-y-4">
          <ConfidenceMeter value={0.82} label="Hoch (>70%)" />
          <ConfidenceMeter value={0.55} label="Mittel (40-70%)" />
          <ConfidenceMeter value={0.28} label="Niedrig (<40%)" />
        </GlowCard>
      </section>

      <Separator />

      {/* ── M4: StockCard variants ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">StockCard – alle Varianten</h2>

        <p className="text-xs text-foreground-muted">compact</p>
        <StockCard stock={aapl} variant="compact" />

        <p className="text-xs text-foreground-muted mt-4">detailed</p>
        <StockCard stock={aapl} variant="detailed" />

        <p className="text-xs text-foreground-muted mt-4">trending</p>
        <div className="grid grid-cols-2 gap-3">
          {TRENDING_STOCKS.slice(0, 2).map((s) => (
            <StockCard key={s.ticker} stock={s} variant="trending" />
          ))}
        </div>
      </section>

      <Separator />

      {/* ── M4: StockList ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          StockList ({STOCKS.length} items)
        </h2>
        <StockList stocks={STOCKS} variant="compact" initialCount={5} />
      </section>

      <Separator />

      {/* ── M4: PriceChart (AAPL) ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          PriceChart – AAPL (mit Zeit-Toggle)
        </h2>
        <GlowCard className="p-4" glow="primary">
          <PriceChart candles={aaplCandles} ticker="AAPL" />
        </GlowCard>
      </section>

      <Separator />

      {/* ── M4: PredictionOverlay (AAPL 30d) ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          PredictionOverlay – AAPL 30d
        </h2>
        <GlowCard className="p-4" glow="accent">
          <PredictionOverlay
            candles={aaplCandles}
            prediction={aaplPred30}
            ticker="AAPL"
          />
        </GlowCard>
      </section>

      <Separator />

      {/* ── Mock-Daten Spot-Check ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">Market Outlook</h2>
        <div className="p-4 rounded-xl bg-accent/10 border border-accent/20">
          <p className="text-xs text-accent font-semibold uppercase tracking-wide mb-1">
            {MARKET_OUTLOOK.sentiment} · Confidence {Math.round(MARKET_OUTLOOK.confidence * 100)}%
          </p>
          <p className="text-sm text-foreground">{MARKET_OUTLOOK.summary}</p>
          <Badge variant="accent" className="mt-2">Updated {new Date(MARKET_OUTLOOK.updatedAt).toLocaleTimeString()}</Badge>
        </div>
      </section>
    </main>
  );
}
