"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 active:scale-[0.97] cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-background font-semibold hover:bg-primary/90 hover:shadow-[0_0_20px_-5px_rgba(0,212,255,0.6)]",
        secondary:
          "bg-surface border border-border text-foreground hover:bg-card hover:border-primary/30",
        ghost:
          "text-foreground-muted hover:bg-card hover:text-foreground",
        danger:
          "bg-danger text-white hover:bg-danger/90",
        outline:
          "border border-border bg-transparent text-foreground hover:bg-card hover:border-primary/40",
        accent:
          "bg-accent text-white hover:bg-accent/90 hover:shadow-[0_0_20px_-5px_rgba(108,99,255,0.5)]",
      },
      size: {
        sm:      "h-8  px-3 text-xs",
        default: "h-10 px-4",
        lg:      "h-12 px-6 text-base",
        icon:    "h-10 w-10 p-0",
        "icon-sm": "h-8 w-8 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
