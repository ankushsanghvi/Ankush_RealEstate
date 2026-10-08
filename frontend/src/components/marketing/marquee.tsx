import { NEIGHBORHOODS } from "@/lib/mock";

export function Marquee() {
  const items = [...NEIGHBORHOODS, ...NEIGHBORHOODS];
  return (
    <div className="marquee relative overflow-hidden border-y border-line bg-surface py-4">
      <div className="pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-surface to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-surface to-transparent" />
      <div className="marquee-track flex w-max gap-10 whitespace-nowrap">
        {items.map((n, i) => (
          <span key={`${n.code}-${i}`} className="inline-flex items-center gap-3 text-[13px] text-ink-2">
            <span className="font-serif text-[17px] text-ink">{n.name}</span>
            <span className="font-mono text-[11px] text-ink-3">{n.code}</span>
            <span className="tabular text-ink-3">median ${(n.median / 1000).toFixed(0)}k</span>
            <span className="h-1 w-1 rounded-full bg-line" />
          </span>
        ))}
      </div>
    </div>
  );
}
