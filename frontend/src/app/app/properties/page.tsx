"use client";
import { useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/app/shell";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { NeighborhoodChart } from "@/components/app/charts";
import { listProperties } from "@/lib/api";
import { NEIGHBORHOODS } from "@/lib/mock";
import type { Property, Neighborhood } from "@/lib/types";
import { usd, num, cn } from "@/lib/utils";
import { ArrowUpDown, Search } from "lucide-react";

type SortKey = keyof Pick<Property, "salePrice" | "grLivArea" | "yearBuilt" | "overallQual" | "neighborhood">;
const nbName = (c: string) => NEIGHBORHOODS.find((n) => n.code === c)?.name ?? c;

export default function PropertiesPage() {
  const [data, setData] = useState<Property[] | null>(null);
  const [mode, setMode] = useState<"live" | "demo">("demo");
  const [q, setQ] = useState("");
  const [nb, setNb] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "salePrice", dir: -1 });
  const [page, setPage] = useState(0);
  const PAGE = 20;

  useEffect(() => { listProperties({}).then((r) => { setData(r.items); setMode(r.mode); }); }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    const term = q.toLowerCase();
    return data
      .filter((p) => (!nb || p.neighborhood === nb) && (!term || p.summary.toLowerCase().includes(term) || p.id.toLowerCase().includes(term)))
      .sort((a, b) => (a[sort.key] > b[sort.key] ? 1 : -1) * sort.dir);
  }, [data, q, nb, sort]);

  const pageRows = rows.slice(page * PAGE, page * PAGE + PAGE);
  const th = (key: SortKey, label: string, right = false) => (
    <th className={cn("px-4 py-2.5 font-medium", right && "text-right")}>
      <button onClick={() => { setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : -1 })); setPage(0); }} className={cn("inline-flex items-center gap-1 hover:text-ink", sort.key === key && "text-ink")}>
        {label} <ArrowUpDown size={11} />
      </button>
    </th>
  );

  return (
    <Shell title="Property records" subtitle="Browse the indexed historical sales that ground every valuation">
      <div className="space-y-5">
        <Card>
          <CardHeader eyebrow="Location analysis" title="Median sale price by neighborhood" subtitle="Ames, Iowa · 25 neighborhoods" />
          <CardBody>
            <NeighborhoodChart data={NEIGHBORHOODS.map((n) => ({ name: n.name, code: n.code, median: n.median }))} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title={<span>Indexed records {data && <span className="ml-1 text-ink-3 font-normal">· {num(rows.length)} matching</span>}</span>}
            action={mode === "demo" ? <Badge tone="warning">demo subset</Badge> : <Badge tone="good">live index</Badge>}
          />
          <CardBody className="space-y-3 px-0 pb-0">
            <div className="flex flex-col gap-2 px-5 sm:flex-row">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
                <Input className="pl-8" placeholder="Search case text or record id…" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
              </div>
              <Select className="sm:w-64" value={nb} onChange={(e) => { setNb(e.target.value as Neighborhood | ""); setPage(0); }}>
                <option value="">All neighborhoods</option>
                {NEIGHBORHOODS.map((n) => <option key={n.code} value={n.code}>{n.name}</option>)}
              </Select>
            </div>
            <div className="overflow-x-auto">
              {!data ? (
                <div className="space-y-2 px-5 pb-5">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>
              ) : (
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-y border-line bg-paper text-left text-[11.5px] uppercase tracking-wider text-ink-3">
                      <th className="px-4 py-2.5 font-medium">Record</th>
                      {th("neighborhood", "Neighborhood")}
                      {th("overallQual", "Qual", true)}
                      <th className="px-4 py-2.5 text-right font-medium">Beds / Baths</th>
                      {th("grLivArea", "Living sq ft", true)}
                      {th("yearBuilt", "Built", true)}
                      <th className="px-4 py-2.5 text-right font-medium">Garage</th>
                      {th("salePrice", "Sale price", true)}
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((p) => (
                      <tr key={p.id} className="border-b border-line-2 transition-colors hover:bg-paper">
                        <td className="px-4 py-2.5 font-mono text-[12px] text-ink-3">{p.id}</td>
                        <td className="px-4 py-2.5 text-ink">{nbName(p.neighborhood)} <span className="font-mono text-[11px] text-ink-3">{p.neighborhood}</span></td>
                        <td className="px-4 py-2.5 text-right tabular text-ink">{p.overallQual}</td>
                        <td className="px-4 py-2.5 text-right tabular text-ink-2">{p.bedroomAbvGr} / {p.fullBath}</td>
                        <td className="px-4 py-2.5 text-right tabular text-ink">{num(p.grLivArea)}</td>
                        <td className="px-4 py-2.5 text-right tabular text-ink-2">{p.yearBuilt}</td>
                        <td className="px-4 py-2.5 text-right tabular text-ink-2">{p.garageCars}</td>
                        <td className="px-4 py-2.5 text-right tabular font-medium text-ink">{usd(p.salePrice)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div className="flex items-center justify-between border-t border-line px-5 py-3 text-[12.5px] text-ink-3">
              <span>Page {page + 1} of {Math.max(1, Math.ceil(rows.length / PAGE))}</span>
              <div className="flex gap-2">
                <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="rounded-full border border-line px-3 py-1 text-ink-2 disabled:opacity-40 hover:bg-surface-2">Previous</button>
                <button disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage((p) => p + 1)} className="rounded-full border border-line px-3 py-1 text-ink-2 disabled:opacity-40 hover:bg-surface-2">Next</button>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </Shell>
  );
}
