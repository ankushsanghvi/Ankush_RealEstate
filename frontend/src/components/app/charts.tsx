"use client";
import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine, LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { usd, usdCompact } from "@/lib/utils";
import type { Comparable } from "@/lib/types";

const tooltipStyle = {
  contentStyle: { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, fontSize: 12, color: "var(--ink)", boxShadow: "var(--shadow-md)" },
  labelStyle: { color: "var(--ink-3)", fontSize: 11 },
  itemStyle: { color: "var(--ink)" },
  cursor: { fill: "var(--line-2)" },
};

/* Horizontal diverging bars: per-feature $ contribution. */
export function ContributionChart({ data }: { data: { feature: string; impact: number }[] }) {
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }} barSize={10}>
          <XAxis type="number" tickFormatter={(v) => usdCompact(v)} tick={{ fontSize: 11, fill: "var(--ink-3)" }} axisLine={{ stroke: "var(--grid)" }} tickLine={false} />
          <YAxis type="category" dataKey="feature" width={92} tick={{ fontSize: 12, fill: "var(--ink-2)" }} axisLine={false} tickLine={false} />
          <ReferenceLine x={0} stroke="var(--ink-3)" />
          <Tooltip {...tooltipStyle} formatter={(v) => [usd(Number(v)), "Contribution"]} />
          <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
            {data.map((d) => <Cell key={d.feature} fill={d.impact >= 0 ? "var(--series-1)" : "var(--series-2)"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* Dot strip of adjusted comparable prices with estimate + band (pure SVG, no library). */
export function ComparableRangeChart({ comparables, estimate, low, high }: { comparables: Comparable[]; estimate: number; low: number; high: number }) {
  const prices = comparables.map((c) => c.adjustedPrice);
  const min = Math.min(low, ...prices) * 0.97;
  const max = Math.max(high, ...prices) * 1.03;
  const x = (v: number) => ((v - min) / (max - min)) * 100;
  const sorted = useMemo(() => [...comparables].sort((a, b) => a.adjustedPrice - b.adjustedPrice), [comparables]);
  return (
    <div>
      <svg viewBox="0 0 100 44" className="h-[120px] w-full overflow-visible" preserveAspectRatio="none">
        <rect x={x(low)} y={6} width={x(high) - x(low)} height={26} rx={2} fill="var(--accent-soft)" />
        <line x1={0} x2={100} y1={32} y2={32} stroke="var(--grid)" strokeWidth={0.4} />
        <line x1={x(estimate)} x2={x(estimate)} y1={2} y2={36} stroke="var(--accent)" strokeWidth={0.6} strokeDasharray="1.5 1" />
        {sorted.map((c, i) => (
          <g key={c.property.id}>
            <circle cx={x(c.adjustedPrice)} cy={19 + ((i % 3) - 1) * 6} r={2.2} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={0.8}>
              <title>{`${c.property.id} · adjusted ${usd(c.adjustedPrice)} (sold ${usd(c.property.salePrice)})`}</title>
            </circle>
          </g>
        ))}
      </svg>
      <div className="flex justify-between font-mono text-[10.5px] text-ink-3 tabular">
        <span>{usdCompact(min)}</span>
        <span className="text-accent-ink">est. {usdCompact(estimate)}</span>
        <span>{usdCompact(max)}</span>
      </div>
    </div>
  );
}

/* Evaluation history lines. */
export function EvalHistoryChart({ data }: { data: { date: string; faithfulness: number; relevancy: number; precision: number }[] }) {
  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: -10, right: 12, top: 8, bottom: 4 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--ink-3)" }} axisLine={{ stroke: "var(--grid)" }} tickLine={false} />
          <YAxis domain={[0.6, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 11, fill: "var(--ink-3)" }} axisLine={false} tickLine={false} />
          <Tooltip {...tooltipStyle} formatter={(v, n) => [`${(Number(v) * 100).toFixed(0)}%`, String(n)]} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} iconType="plainline" />
          <Line type="monotone" dataKey="faithfulness" isAnimationActive={false} name="Faithfulness" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3.5, strokeWidth: 2, stroke: "var(--surface)" }} activeDot={{ r: 5 }} />
          <Line type="monotone" dataKey="relevancy" isAnimationActive={false} name="Answer relevancy" stroke="var(--series-2)" strokeWidth={2} dot={{ r: 3.5, strokeWidth: 2, stroke: "var(--surface)" }} activeDot={{ r: 5 }} />
          <Line type="monotone" dataKey="precision" isAnimationActive={false} name="Contextual precision" stroke="var(--series-3)" strokeWidth={2} dot={{ r: 3.5, strokeWidth: 2, stroke: "var(--surface)" }} activeDot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* Neighborhood median bars. */
export function NeighborhoodChart({ data }: { data: { name: string; code: string; median: number }[] }) {
  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: -6, right: 8, top: 8, bottom: 28 }} barSize={14}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="code" interval={0} angle={-45} textAnchor="end" tick={{ fontSize: 10.5, fill: "var(--ink-3)", fontFamily: "var(--font-mono)" }} axisLine={{ stroke: "var(--grid)" }} tickLine={false} />
          <YAxis tickFormatter={(v) => usdCompact(v)} tick={{ fontSize: 11, fill: "var(--ink-3)" }} axisLine={false} tickLine={false} />
          <Tooltip {...tooltipStyle} formatter={(v) => [usd(Number(v)), "Median sale price"]} labelFormatter={(_, payload) => (payload?.[0]?.payload as { name?: string } | undefined)?.name ?? ""} />
          <Bar dataKey="median" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
