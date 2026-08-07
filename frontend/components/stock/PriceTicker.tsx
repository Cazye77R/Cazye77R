"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/lib/format";

interface PriceTickerProps {
  price: number;
  className?: string;
}

export default function PriceTicker({ price, className }: PriceTickerProps) {
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const prev = useRef(price);

  useEffect(() => {
    if (price !== prev.current) {
      setFlash(price > prev.current ? "up" : "down");
      prev.current = price;
      const id = setTimeout(() => setFlash(null), 600);
      return () => clearTimeout(id);
    }
  }, [price]);

  return (
    <span
      className={cn(
        "font-mono font-bold tabular-nums transition-colors duration-300",
        flash === "up"   && "text-success",
        flash === "down" && "text-danger",
        flash === null   && "text-foreground",
        className
      )}
      aria-live="polite"
      aria-atomic
    >
      {formatPrice(price)}
    </span>
  );
}
