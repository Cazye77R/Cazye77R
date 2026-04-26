export default async function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  return <main className="p-8"><h1 className="text-2xl font-bold text-foreground">Stock: {ticker}</h1><p className="text-foreground-muted mt-2">Milestone 4+</p></main>;
}
