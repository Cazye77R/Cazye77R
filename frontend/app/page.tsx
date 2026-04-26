/**
 * Home Dashboard – placeholder until Milestone 5.
 * Shows the design system is wired up correctly.
 */

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-8 p-8">
      {/* Logo */}
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          StockMind
        </h1>
        <p className="mt-2 text-foreground-muted text-sm">
          AI-powered Stock Analytics · Milestone 1 ✓
        </p>
      </div>

      {/* Design system smoke test */}
      <div className="w-full max-w-sm space-y-4">
        {/* Glassmorphism card */}
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-foreground-muted mb-1">Design System</p>
          <div className="flex flex-wrap gap-2 mt-3">
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
          <div className="mt-4 font-mono text-xl text-foreground num">
            $1,234.56 <span className="text-success text-sm">+2.34%</span>
          </div>
        </div>

        {/* Glow test */}
        <div className="rounded-xl bg-card border border-border p-4 transition-all duration-200 hover:glow-primary hover:-translate-y-0.5">
          <p className="text-sm text-foreground-muted">
            Hover me → glow effect
          </p>
        </div>
      </div>
    </main>
  );
}
