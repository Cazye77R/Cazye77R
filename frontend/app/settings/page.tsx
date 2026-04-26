"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { Moon, Sun, Monitor, Cpu, Brain } from "lucide-react";
import type { AiProvider } from "@/lib/types";

type ThemeOption = "dark" | "light" | "system";

const THEME_OPTS: { value: ThemeOption; label: string; Icon: typeof Moon }[] = [
  { value: "dark",   label: "Dunkel", Icon: Moon    },
  { value: "light",  label: "Hell",   Icon: Sun     },
  { value: "system", label: "System", Icon: Monitor },
];

const PROVIDER_OPTS: { value: AiProvider; label: string; desc: string; Icon: typeof Cpu }[] = [
  { value: "ollama", label: "Ollama",      desc: "Lokal, kostenlos",   Icon: Cpu   },
  { value: "nvidia", label: "NVIDIA NIM",  desc: "Cloud-API, schnell", Icon: Brain },
];

type Language = "de" | "en";
const LANG_OPTS: { value: Language; label: string; flag: string }[] = [
  { value: "de", label: "Deutsch",  flag: "🇩🇪" },
  { value: "en", label: "English",  flag: "🇬🇧" },
];

function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3" aria-labelledby={`section-${title}`}>
      <h2
        id={`section-${title}`}
        className="text-xs font-semibold text-foreground-muted uppercase tracking-widest"
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [provider, setProvider] = useState<AiProvider>("ollama");
  const [language, setLanguage] = useState<Language>("de");

  return (
    <div className="mx-auto max-w-md px-4 py-6 space-y-8">
      <h1 className="text-xl font-bold text-foreground">Einstellungen</h1>

      {/* ── Theme ── */}
      <SettingsSection title="Darstellung">
        <div className="grid grid-cols-3 gap-2" role="group" aria-label="Theme auswählen">
          {THEME_OPTS.map(({ value, label, Icon }) => (
            <button
              key={value}
              onClick={() => setTheme(value)}
              aria-pressed={theme === value}
              className={cn(
                "flex flex-col items-center gap-1.5 rounded-xl border py-3 transition-all duration-200",
                theme === value
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-surface text-foreground-muted hover:bg-card hover:text-foreground"
              )}
            >
              <Icon className="size-5" aria-hidden />
              <span className="text-xs font-medium">{label}</span>
            </button>
          ))}
        </div>
      </SettingsSection>

      {/* ── AI Provider ── */}
      <SettingsSection title="KI-Provider">
        <div className="space-y-2" role="group" aria-label="KI-Provider wählen">
          {PROVIDER_OPTS.map(({ value, label, desc, Icon }) => (
            <button
              key={value}
              onClick={() => setProvider(value)}
              aria-pressed={provider === value}
              className={cn(
                "w-full flex items-center gap-4 rounded-xl border px-4 py-3.5 transition-all duration-200 text-left",
                provider === value
                  ? "border-accent/40 bg-accent/10"
                  : "border-border bg-surface hover:bg-card"
              )}
            >
              <span
                className={cn(
                  "flex items-center justify-center size-9 rounded-lg shrink-0",
                  provider === value ? "bg-accent/20 text-accent" : "bg-border text-foreground-muted"
                )}
              >
                <Icon className="size-5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    "text-sm font-semibold",
                    provider === value ? "text-accent" : "text-foreground"
                  )}
                >
                  {label}
                </p>
                <p className="text-xs text-foreground-muted">{desc}</p>
              </div>
              <span
                className={cn(
                  "size-4 rounded-full border-2 shrink-0 transition-all",
                  provider === value
                    ? "border-accent bg-accent"
                    : "border-border"
                )}
              />
            </button>
          ))}
        </div>
        <p className="text-xs text-foreground-muted px-1">
          Die Backend-Anbindung erfolgt in einem späteren Schritt über eine FastAPI-Brücke.
        </p>
      </SettingsSection>

      {/* ── Language ── */}
      <SettingsSection title="Sprache">
        <div className="flex gap-2" role="group" aria-label="Sprache wählen">
          {LANG_OPTS.map(({ value, label, flag }) => (
            <button
              key={value}
              onClick={() => setLanguage(value)}
              aria-pressed={language === value}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 rounded-xl border py-3 transition-all duration-200",
                language === value
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-surface text-foreground-muted hover:bg-card hover:text-foreground"
              )}
            >
              <span>{flag}</span>
              <span className="text-sm font-medium">{label}</span>
            </button>
          ))}
        </div>
      </SettingsSection>

      {/* ── About ── */}
      <SettingsSection title="Über StockMind">
        <div className="rounded-xl border border-border bg-surface p-4 space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-foreground-muted">Version</span>
            <span className="font-mono text-foreground">0.1.0-alpha</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Framework</span>
            <span className="font-mono text-foreground">Next.js 16</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">UI</span>
            <span className="font-mono text-foreground">Tailwind v4 + shadcn</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Charts</span>
            <span className="font-mono text-foreground">Recharts 3</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Backend</span>
            <span className="font-mono text-foreground-muted italic">FastAPI (ausstehend)</span>
          </div>
        </div>
      </SettingsSection>
    </div>
  );
}
