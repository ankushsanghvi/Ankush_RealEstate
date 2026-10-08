"use client";
import { useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/app/shell";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Select, Label } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { compareProperties, listProperties } from "@/lib/api";
import { NEIGHBORHOODS } from "@/lib/mock";
import type { CompareFactor, Property } from "@/lib/types";
import { usd, num, pct, cn } from "@/lib/utils";
import { ArrowRight } from "lucide-react";

const nbName = (c: string) => NEIGHBORHOODS.find((n) => n.code === c)?.name ?? c;
const nbMedian = (c: string) => NEIGHBORHOODS.find((n) => n.code === c)?.median ?? 180000;

const ROWS: { key: keyof Property; label: string; fmt?: (v: number) => string }[] = [
  { key: "salePrice", label: "Sale price", fmt: usd },
  { key: "neighborhood", label: "Neighborhood" },
  { key: "overallQual", label: "Overall quality" },
  { key: "overallCond", label: "Overall condition" },
  { key: "grLivArea", label: "Living area (sq ft)", fmt: num },
  { key: "totalBsmtSF", label: "Basement (sq ft)", fmt: num },
  { key: "lotArea", label: "Lot area (sq ft)", fmt: num },
  { key: "yearBuilt", label: "Year built" },
  { key: "yearRemodAdd", label: "Remodel year" },
  { key: "bedroomAbvGr", label: "Bedrooms" },
  { key: "fullBath", label: "Full baths" },
  { key: "totRmsAbvGrd", label: "Total rooms" },
  { key: "garageCars", label: "Garage (cars)" },
  { key: "saleYear", label: "Sale year" },
];

/** Local approximation used only when the API is unreachable (demo mode). */
function localFactors(pa: Property, pb: Property): { diff: number; list: CompareFactor[]; explained: number; narrative: string } {
  const diff = pb.salePrice - pa.salePrice;
  const ppsf = (pa.salePrice / pa.grLivArea + pb.salePrice / pb.grLivArea) / 2;
  const list: CompareFactor[] = [
    { label: "Neighborhood premium", amount: Math.round((nbMedian(pb.neighborhood) - nbMedian(pa.neighborhood)) * 0.6), why: `${nbName(pb.neighborhood)} vs ${nbName(pa.neighborhood)} median` },
    { label: "Living area", amount: Math.round((pb.grLivArea - pa.grLivArea) * ppsf * 0.6), why: `${num(pb.grLivArea)} vs ${num(pa.grLivArea)} sq ft` },
    { label: "Quality grade", amount: (pb.overallQual - pa.overallQual) * 9500, why: `Q${pb.overallQual} vs Q${pa.overallQual}` },
    { label: "Age / construction year", amount: (pb.yearBuilt - pa.yearBuilt) * 420, why: `${pb.yearBuilt} vs ${pa.yearBuilt}` },
    { label: "Garage capacity", amount: (pb.garageCars - pa.garageCars) * 7800, why: `${pb.garageCars} vs ${pa.garageCars} cars` },
    { label: "Basement area", amount: Math.round((pb.totalBsmtSF - pa.totalBsmtSF) * 18), why: `${num(pb.totalBsmtSF)} vs ${num(pa.totalBsmtSF)} sq ft` },
  ];
  const explained = list.reduce((s, f) => s + f.amount, 0);
  list.push({ label: "Unexplained / market noise", amount: diff - explained, why: "Timing, condition details, lot shape, sale type" });
  return { diff, list: list.sort((x, y) => Math.abs(y.amount) - Math.abs(x.amount)), explained, narrative: "Local approximation (API unreachable)." };
}

export default function ComparePage() {
  const [props, setProps] = useState<Property[] | null>(null);
  const [mode, setMode] = useState<"live" | "demo">("demo");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [result, setResult] = useState<{ diff: number; list: CompareFactor[]; explained: number; narrative: string; live: boolean } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listProperties({}).then((r) => {
      setProps(r.items);
      setMode(r.mode);
      setA(r.items[12]?.id ?? r.items[0]?.id ?? "");
      setB(r.items[57]?.id ?? r.items[1]?.id ?? "");
    });
  }, []);

  const pa = useMemo(() => props?.find((p) => p.id === a), [props, a]);
  const pb = useMemo(() => props?.find((p) => p.id === b), [props, b]);

  useEffect(() => {
    if (!pa || !pb) return;
    let alive = true;
    setLoading(true);
    compareProperties(pa.id, pb.id).then((r) => {
      if (!alive) return;
      if (r) setResult({ diff: r.difference, list: r.factors, explained: r.factors.filter((f) => f.label !== "Unexplained / market noise").reduce((s, f) => s + f.amount, 0), narrative: r.narrative, live: true });
      else setResult({ ...localFactors(pa, pb), live: false });
      setLoading(false);
    });
    return () => { alive = false; };
  }, [pa, pb]);

  const maxAbs = Math.max(...(result?.list.map((f) => Math.abs(f.amount)) ?? [1]), 1);

  return (
    <Shell title="Compare properties" subtitle="Explain why two similar homes sold for different prices">
      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <Card>
            <CardBody className="grid gap-4 pt-5 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
              <div>
                <Label>Property A</Label>
                <Select value={a} onChange={(e) => setA(e.target.value)} disabled={!props}>
                  {(props ?? []).map((p) => <option key={p.id} value={p.id}>{p.id} · {nbName(p.neighborhood)} · {usd(p.salePrice)}</option>)}
                </Select>
              </div>
              <ArrowRight size={18} className="mx-auto mb-2 hidden text-ink-3 sm:block" />
              <div>
                <Label>Property B</Label>
                <Select value={b} onChange={(e) => setB(e.target.value)} disabled={!props}>
                  {(props ?? []).map((p) => <option key={p.id} value={p.id}>{p.id} · {nbName(p.neighborhood)} · {usd(p.salePrice)}</option>)}
                </Select>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader eyebrow="Side by side" title="Attribute comparison" action={mode === "live" ? <Badge tone="good">live index</Badge> : <Badge tone="warning">demo subset</Badge>} />
            <CardBody className="overflow-x-auto px-0 pb-0">
              {!pa || !pb ? (
                <div className="space-y-2 px-5 pb-5">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-8" />)}</div>
              ) : (
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-y border-line bg-paper text-left text-[11.5px] uppercase tracking-wider text-ink-3">
                      <th className="px-5 py-2 font-medium">Attribute</th>
                      <th className="px-5 py-2 font-medium">{pa.id}</th>
                      <th className="px-5 py-2 font-medium">{pb.id}</th>
                      <th className="px-5 py-2 text-right font-medium">Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ROWS.map((r) => {
                      const va = pa[r.key] as number | string;
                      const vb = pb[r.key] as number | string;
                      const isNum = typeof va === "number" && typeof vb === "number";
                      const d = isNum ? (vb as number) - (va as number) : 0;
                      const show = (v: number | string) => (typeof v === "number" && r.fmt ? r.fmt(v) : r.key === "neighborhood" ? nbName(String(v)) : String(v));
                      return (
                        <tr key={r.key} className="border-b border-line-2">
                          <td className="px-5 py-2 text-ink-2">{r.label}</td>
                          <td className="px-5 py-2 tabular text-ink">{show(va)}</td>
                          <td className="px-5 py-2 tabular text-ink">{show(vb)}</td>
                          <td className={cn("px-5 py-2 text-right tabular", d > 0 ? "text-[color:var(--delta-good-text)]" : d < 0 ? "text-critical" : "text-ink-3")}>
                            {isNum ? (d === 0 ? "—" : `${d > 0 ? "+" : ""}${r.fmt ? r.fmt(d) : d}`) : va === vb ? "same" : "differs"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader
              eyebrow="Price difference"
              title={result ? <span className="tabular">{result.diff >= 0 ? "+" : ""}{usd(result.diff)}</span> : "—"}
              subtitle={result && pa ? `B relative to A · ${pct(result.diff / pa.salePrice, 1)}` : "Select two records"}
              action={result && <Badge tone={result.live ? "sky" : "warning"}>{result.live ? "hedonic model" : "local approx."}</Badge>}
            />
            <CardBody className={cn("space-y-3", loading && "opacity-60")}>
              {!result ? (
                <Skeleton className="h-48" />
              ) : (
                <>
                  {result.list.map((f) => (
                    <div key={f.label}>
                      <div className="mb-1 flex items-center justify-between text-[13px]">
                        <span className="text-ink">{f.label}</span>
                        <span className={cn("tabular", f.amount > 0 ? "text-[color:var(--delta-good-text)]" : f.amount < 0 ? "text-critical" : "text-ink-3")}>{f.amount > 0 ? "+" : ""}{usd(f.amount)}</span>
                      </div>
                      <Meter value={Math.abs(f.amount) / maxAbs} color={f.amount >= 0 ? "var(--series-1)" : "var(--series-2)"} />
                      <div className="mt-1 text-[11.5px] text-ink-3">{f.why}</div>
                    </div>
                  ))}
                  <div className="border-t border-line-2 pt-3 text-[12.5px] leading-relaxed text-ink-2">
                    <Badge tone="sky" className="mr-2">Explained</Badge>{pct(Math.min(1, Math.abs(result.explained) / Math.max(1, Math.abs(result.diff))), 0)} of the gap attributed to measurable attributes.
                    {result.live && <p className="mt-2 text-ink-2">{result.narrative}</p>}
                  </div>
                </>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </Shell>
  );
}
