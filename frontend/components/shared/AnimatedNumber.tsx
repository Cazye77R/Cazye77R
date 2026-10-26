"use client";

import { useEffect, useRef, useState } from "react";
import { useSpring, useMotionValue, animate } from "framer-motion";
import { cn } from "@/lib/utils";
import { formatPrice, formatPercent, formatLargeNumber, formatNumber } from "@/lib/format";

type FormatKind = "currency" | "percent" | "compact" | "number";

interface AnimatedNumberProps {
  value: number;
  format?: FormatKind;
  /** Currency code – only used when format="currency" */
  currency?: string;
  /** Decimal places – only used when format="number" */
  decimals?: number;
  /** Spring stiffness (lower = slower). Default 80 */
  stiffness?: number;
  /** Spring damping. Default 20 */
  damping?: number;
  className?: string;
}

export default function AnimatedNumber({
  value,
  format = "number",
  currency = "USD",
  decimals = 2,
  stiffness = 80,
  damping = 20,
  className,
}: AnimatedNumberProps) {
  const motionValue = useMotionValue(value);
  const spring = useSpring(motionValue, { stiffness, damping });
  const [display, setDisplay] = useState(() => fmt(value, format, currency, decimals));
  const prevValue = useRef(value);

  // Kick off animation when value changes
  useEffect(() => {
    if (prevValue.current !== value) {
      prevValue.current = value;
      const controls = animate(motionValue, value, {
        type: "spring",
        stiffness,
        damping,
      });
      return () => controls.stop();
    }
  }, [value, stiffness, damping, motionValue]);

  // Update display string on every spring tick
  useEffect(() => {
    return spring.on("change", (v) => {
      setDisplay(fmt(v, format, currency, decimals));
    });
  }, [spring, format, currency, decimals]);

  return (
    <span
      className={cn("num tabular-nums", className)}
      aria-label={String(value)}
    >
      {display}
    </span>
  );
}

function fmt(v: number, kind: FormatKind, currency: string, decimals: number): string {
  switch (kind) {
    case "currency": return formatPrice(v, currency);
    case "percent":  return formatPercent(v, true);
    case "compact":  return formatLargeNumber(v);
    default:         return formatNumber(v, decimals);
  }
}
