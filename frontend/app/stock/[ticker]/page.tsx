import type { Metadata } from "next";

// In Next.js 16, params is always a Promise
export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  return { title: ticker.toUpperCase() };
}

export default async function StockPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-foreground">{ticker.toUpperCase()}</h1>
      <p className="text-foreground-muted mt-2 text-sm">
        Stock detail vollständig in Milestone 4+5.
      </p>
    </div>
  );
}
