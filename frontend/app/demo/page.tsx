/**
 * Milestone 2 – Component showcase page.
 * Visible at /demo during development. Not linked from nav.
 */
import { Separator } from "@/components/ui/separator";
import { Badge }     from "@/components/ui/badge";
import AnimatedNumber  from "@/components/shared/AnimatedNumber";
import ChangeBadge     from "@/components/shared/ChangeBadge";
import GlowCard        from "@/components/shared/GlowCard";
import AiThinking      from "@/components/ai/AiThinking";
import ConfidenceMeter from "@/components/ai/ConfidenceMeter";
import { STOCKS, MARKET_OUTLOOK, TRENDING_STOCKS } from "@/lib/mock-data";

export default function DemoPage() {
  const aapl = STOCKS.find((s) => s.ticker === "AAPL")!;

  return (
    <main className="min-h-screen p-6 space-y-10 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
        Milestone 2 – Component Demo
      </h1>

      {/* ── AnimatedNumber ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          AnimatedNumber
        </h2>
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

      {/* ── ChangeBadge ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          ChangeBadge
        </h2>
        <div className="flex flex-wrap gap-3 items-center">
          <ChangeBadge value={0.0234} variant="compact" />
          <ChangeBadge value={-0.0318} variant="compact" />
          <ChangeBadge value={0}      variant="compact" />
          <ChangeBadge value={0.0181} variant="full" />
          <ChangeBadge value={-0.0222} variant="full" />
        </div>
      </section>

      <Separator />

      {/* ── GlowCard ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          GlowCard (hover me)
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {(["primary", "accent", "success", "danger"] as const).map((glow) => (
            <GlowCard key={glow} glow={glow} className="p-4">
              <p className="text-xs text-foreground-muted">glow=&quot;{glow}&quot;</p>
              <p className="text-foreground font-semibold mt-1 capitalize">{glow} Glow</p>
            </GlowCard>
          ))}
          <GlowCard glass className="p-4 col-span-2" glow="primary">
            <p className="text-xs text-foreground-muted">glass=true + glow=&quot;primary&quot;</p>
            <p className="text-foreground font-medium mt-1">Glassmorphism card</p>
          </GlowCard>
        </div>
      </section>

      <Separator />

      {/* ── AiThinking ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          AiThinking
        </h2>
        <GlowCard className="p-4 flex items-center justify-center" glow="accent">
          <AiThinking label="Modell lädt Vorhersage…" />
        </GlowCard>
        <GlowCard className="p-4 flex items-center justify-center">
          <AiThinking />
        </GlowCard>
      </section>

      <Separator />

      {/* ── ConfidenceMeter ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          ConfidenceMeter
        </h2>
        <GlowCard className="p-5 space-y-4">
          <ConfidenceMeter value={0.82} label="Hoch (>70%)" />
          <ConfidenceMeter value={0.55} label="Mittel (40-70%)" />
          <ConfidenceMeter value={0.28} label="Niedrig (<40%)" />
        </GlowCard>
      </section>

      <Separator />

      {/* ── Mock data spot-check ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground-muted uppercase tracking-widest">
          Mock-Daten ({STOCKS.length} Aktien)
        </h2>
        <div className="space-y-2">
          {TRENDING_STOCKS.map((s) => (
            <div key={s.ticker} className="flex items-center justify-between p-3 rounded-lg bg-surface border border-border">
              <div className="flex items-center gap-3">
                <span className="text-xl">{s.logo}</span>
                <div>
                  <p className="text-sm font-semibold text-foreground">{s.ticker}</p>
                  <p className="text-xs text-foreground-muted">{s.name}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-mono text-foreground">${s.price.toFixed(2)}</p>
                <ChangeBadge value={s.changePercent} />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 p-4 rounded-lg bg-accent/10 border border-accent/20">
          <p className="text-xs text-accent font-semibold uppercase tracking-wide mb-1">
            Market Outlook · {MARKET_OUTLOOK.sentiment}
          </p>
          <p className="text-sm text-foreground">{MARKET_OUTLOOK.summary}</p>
          <Badge variant="accent" className="mt-2">
            Confidence {Math.round(MARKET_OUTLOOK.confidence * 100)}%
          </Badge>
        </div>
      </section>
    </main>
  );
}
