import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dashboard" };

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center gap-8 p-8 pt-12">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          StockMind
        </h1>
        <p className="mt-2 text-foreground-muted text-sm">
          AI-powered Stock Analytics · Dashboard kommt in Milestone 5
        </p>
      </div>

      {/* Design system smoke test */}
      <div className="w-full max-w-sm space-y-3">
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-foreground-muted mb-3">Design Tokens</p>
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["bg-primary", "Primary"],
                ["bg-success", "Success"],
                ["bg-danger",  "Danger"],
                ["bg-accent",  "Accent"],
              ] as const
            ).map(([cls, label]) => (
              <span
                key={label}
                className={`${cls} text-background text-xs font-mono px-2 py-1 rounded-full`}
              >
                {label}
              </span>
            ))}
          </div>
          <div className="mt-4 font-mono text-xl text-foreground">
            $1,234.56{" "}
            <span className="text-success text-sm">+2.34%</span>
          </div>
        </div>

        <div className="rounded-xl bg-card border border-border p-4 transition-all duration-200 hover:shadow-[0_0_30px_-5px_rgba(0,212,255,0.4)] hover:border-primary/30 hover:-translate-y-0.5">
          <p className="text-sm text-foreground-muted">
            Navigation und Header ↑ · BottomNav ↓ · Milestone 3 ✓
          </p>
        </div>
      </div>
    </div>
  );
}
