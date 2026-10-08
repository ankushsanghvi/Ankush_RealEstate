import { cn, clamp } from "@/lib/utils";

/** Thin horizontal meter. `value` is 0–1. Color is a CSS var name. */
export function Meter({ value, color = "var(--series-1)", className, track = true }: { value: number; color?: string; className?: string; track?: boolean }) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full", track && "bg-surface-2", className)} role="meter" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full transition-[width] duration-700 ease-out" style={{ width: `${clamp(value, 0, 1) * 100}%`, background: color }} />
    </div>
  );
}

export function Stat({ label, value, hint, className }: { label: string; value: React.ReactNode; hint?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-[12px] text-ink-3">{label}</span>
      <span className="text-[22px] font-semibold tracking-tight text-ink leading-none">{value}</span>
      {hint && <span className="text-[12px] text-ink-3">{hint}</span>}
    </div>
  );
}
