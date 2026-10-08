import * as React from "react";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "accent" | "sage" | "sky" | "sun" | "good" | "warning" | "critical" | "outline";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-ink-2 border-line",
  accent: "bg-accent-soft text-accent-ink border-transparent",
  sage: "bg-sage-soft text-[color:var(--sage)] border-transparent",
  sky: "bg-sky-soft text-[color:var(--sky)] border-transparent",
  sun: "bg-sun-soft text-[color:var(--sun)] border-transparent",
  good: "bg-sage-soft text-[color:var(--delta-good-text)] border-transparent",
  warning: "bg-sun-soft text-[color:var(--sun)] border-transparent",
  critical: "bg-[color:var(--critical-soft)] text-[color:var(--status-critical)] border-transparent",
  outline: "bg-transparent text-ink-2 border-line",
};

export function Badge({ className, tone = "neutral", children, ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[12px] font-medium leading-5",
        tones[tone],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
