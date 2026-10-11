"use client";

import { useState } from "react";
import type { Stock } from "@/lib/types";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import StockCard from "@/components/stock/StockCard";

interface TopMoversProps {
  stocks: Stock[];
}

export default function TopMovers({ stocks }: TopMoversProps) {
  const [tab, setTab] = useState("gainers");

  const gainers = [...stocks]
    .filter((s) => s.changePercent > 0)
    .sort((a, b) => b.changePercent - a.changePercent)
    .slice(0, 5);

  const losers = [...stocks]
    .filter((s) => s.changePercent < 0)
    .sort((a, b) => a.changePercent - b.changePercent)
    .slice(0, 5);

  const active = [...stocks]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 5);

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList className="w-full">
        <TabsTrigger value="gainers"  className="flex-1">🚀 Gewinner</TabsTrigger>
        <TabsTrigger value="losers"   className="flex-1">📉 Verlierer</TabsTrigger>
        <TabsTrigger value="active"   className="flex-1">🔥 Aktiv</TabsTrigger>
      </TabsList>

      {[
        { value: "gainers", list: gainers },
        { value: "losers",  list: losers  },
        { value: "active",  list: active  },
      ].map(({ value, list }) => (
        <TabsContent key={value} value={value} className="space-y-2 mt-3">
          {list.map((s) => (
            <StockCard key={s.ticker} stock={s} variant="compact" />
          ))}
        </TabsContent>
      ))}
    </Tabs>
  );
}
