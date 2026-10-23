import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type GlowVariant = "primary" | "accent" | "success" | "danger" | "none";

interface GlowCardProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: GlowVariant;
  /** Use glassmorphism background instead of solid card */
  glass?: boolean;
}

const GLOW_HOVER: Record<GlowVariant, string> = {
  primary: "hover:shadow-[0_0_30px_-5px_rgba(0,212,255,0.4)] hover:border-primary/30",
  accent:  "hover:shadow-[0_0_30px_-5px_rgba(108,99,255,0.4)] hover:border-accent/30",
  success: "hover:shadow-[0_0_30px_-5px_rgba(0,255,136,0.4)] hover:border-success/30",
  danger:  "hover:shadow-[0_0_30px_-5px_rgba(255,59,59,0.4)]  hover:border-danger/30",
  none:    "",
};

const GlowCard = forwardRef<HTMLDivElement, GlowCardProps>(
  ({ className, glow = "none", glass = false, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-xl border border-border transition-all duration-200",
          glass ? "glass" : "bg-card",
          "hover:-translate-y-0.5",
          GLOW_HOVER[glow],
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);
GlowCard.displayName = "GlowCard";

export default GlowCard;
