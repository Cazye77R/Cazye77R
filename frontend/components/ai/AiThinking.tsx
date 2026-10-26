"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AiThinkingProps {
  label?: string;
  className?: string;
}

const DOT_VARIANTS = {
  animate: (i: number) => ({
    y: [0, -8, 0],
    opacity: [0.4, 1, 0.4],
    transition: {
      duration: 0.9,
      repeat: Infinity,
      delay: i * 0.18,
      ease: "easeInOut" as const,
    },
  }),
};

export default function AiThinking({
  label = "AI analysiert…",
  className,
}: AiThinkingProps) {
  return (
    <div
      className={cn("flex items-center gap-3 text-foreground-muted", className)}
      role="status"
      aria-label={label}
    >
      <span className="flex items-end gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            custom={i}
            variants={DOT_VARIANTS}
            animate="animate"
            className="block size-2 rounded-full bg-primary"
          />
        ))}
      </span>
      {label && (
        <span className="text-sm font-medium text-foreground-muted">
          {label}
        </span>
      )}
    </div>
  );
}
