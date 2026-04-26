import type { Metadata } from "next";

export const metadata: Metadata = { title: "Markets" };

export default function MarketsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-foreground">Markets</h1>
      <p className="text-foreground-muted mt-2 text-sm">Vollständig in Milestone 5.</p>
    </div>
  );
}
