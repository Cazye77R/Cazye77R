"use client";

/**
 * Page transition wrapper for Next.js App Router.
 * Uses enter-only animation (fade + 12px slide-up) because App Router
 * removes outgoing page children synchronously – exit animations are
 * unreliable without additional infrastructure.
 */

import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

interface PageTransitionProps {
  children: React.ReactNode;
}

export default function PageTransition({ children }: PageTransitionProps) {
  const pathname = usePathname();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
        className="pb-20"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
