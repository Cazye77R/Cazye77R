# StockMind – Frontend

Next.js 16 (App Router, Turbopack) · React 19 · Tailwind v4 · Recharts · zustand.

> Hinweis: Dieses Next.js hat Breaking Changes gegenüber älteren Versionen
> (z. B. ist `params` ein Promise). Siehe `AGENTS.md` und
> `node_modules/next/dist/docs/`.

## Start

```bash
npm install
npm run dev      # http://localhost:3000
npm run lint
npm run build
```

## Daten

Aktuell läuft die App **vollständig auf Mock-Daten** (`lib/mock-data.ts`).
Alle Seiten lesen ausschließlich über `lib/api/stocks.ts`; für einen echten
Backend-Anschluss müssen nur die Funktionen in dieser Datei ersetzt werden
(und die Konsumenten Lade-/Fehlerzustände bekommen, da sie heute synchron
arbeiten). `NEXT_PUBLIC_API_BASE_URL` in `.env.example` ist dafür reserviert,
wird aber noch nicht gelesen.

## Struktur

- `app/` – Routen (`/`, `/markets`, `/stock/[ticker]`, `/ai`, `/watchlist`, `/settings`, `/demo` nur in Dev)
- `components/` – UI (`ui/`, `stock/`, `charts/`, `layout/`, `ai/`, `home/`, `shared/`)
- `store/watchlist-store.ts` – zustand-Store mit `persist` (`skipHydration` + `WatchlistHydrator`, um Hydration-Mismatches zu vermeiden)
- `lib/` – Typen, Formatierung, Mock-Daten, API-Schicht
