"use client";

import { Children, isValidElement, type ReactNode } from "react";
import { motion } from "framer-motion";

const CONTAINER = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.055,
      delayChildren:   0,
    },
  },
};

const ITEM_VISIBLE = {
  hidden:  { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y:       0,
    transition: { duration: 0.24, ease: [0.22, 1, 0.36, 1] as const },
  },
};

// Items beyond this index appear instantly (no stagger delay)
const STAGGER_CUTOFF = 5;

interface AnimatedListProps {
  children: ReactNode;
  /** Outer wrapper element type. Default "ul" */
  as?: "ul" | "div";
  className?: string;
  listItemClassName?: string;
}

export default function AnimatedList({
  children,
  as: Tag = "ul",
  className,
  listItemClassName,
}: AnimatedListProps) {
  const items = Children.toArray(children).filter(isValidElement);

  return (
    <motion.div
      // Cast to satisfy TS – motion.div renders as the semantic Tag via CSS
      role={Tag === "ul" ? "list" : undefined}
      className={className}
      variants={CONTAINER}
      initial="hidden"
      animate="visible"
    >
      {items.map((child, i) =>
        i < STAGGER_CUTOFF ? (
          <motion.div
            key={(child as React.ReactElement<{ key?: string | null }>).key ?? i}
            variants={ITEM_VISIBLE}
            role={Tag === "ul" ? "listitem" : undefined}
            className={listItemClassName}
          >
            {child}
          </motion.div>
        ) : (
          // Beyond cutoff: render without stagger animation wrapper
          <div
            key={(child as React.ReactElement<{ key?: string | null }>).key ?? i}
            role={Tag === "ul" ? "listitem" : undefined}
            className={listItemClassName}
          >
            {child}
          </div>
        )
      )}
    </motion.div>
  );
}
