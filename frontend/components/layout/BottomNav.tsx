"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BarChart3, Sparkles, Bookmark, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/",          label: "Home",      Icon: Home      },
  { href: "/markets",   label: "Markets",   Icon: BarChart3  },
  { href: "/ai",        label: "AI",        Icon: Sparkles   },
  { href: "/watchlist", label: "Watchlist", Icon: Bookmark   },
  { href: "/settings",  label: "Settings",  Icon: Settings   },
] as const;

export default function BottomNav() {
  const pathname = usePathname();

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <nav
      className="fixed bottom-0 inset-x-0 z-50 glass border-t border-border/60"
      aria-label="Main navigation"
    >
      {/* Center on desktop, full-width on mobile */}
      <div className="mx-auto flex max-w-md items-center justify-around px-2 h-16">
        {NAV_ITEMS.map(({ href, label, Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 py-1 rounded-lg",
                "transition-all duration-200 group",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset"
              )}
              aria-label={label}
              aria-current={active ? "page" : undefined}
            >
              <span
                className={cn(
                  "flex items-center justify-center size-8 rounded-lg transition-all duration-200",
                  active
                    ? "bg-primary/15 text-primary shadow-[0_0_12px_-3px_rgba(0,212,255,0.6)]"
                    : "text-foreground-muted group-hover:text-foreground group-hover:bg-card"
                )}
              >
                <Icon className="size-5" aria-hidden />
              </span>
              <span
                className={cn(
                  "text-[10px] font-medium leading-none transition-colors duration-200",
                  active ? "text-primary" : "text-foreground-muted group-hover:text-foreground"
                )}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
