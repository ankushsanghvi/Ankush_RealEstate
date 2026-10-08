"use client";
import { SlidersHorizontal, RotateCcw } from "lucide-react";
import { Input, Label, Select } from "@/components/ui/input";
import { NEIGHBORHOODS } from "@/lib/mock";
import type { QueryFilters, Neighborhood } from "@/lib/types";

export function FilterPanel({ value, onChange }: { value: QueryFilters; onChange: (f: QueryFilters) => void }) {
  const set = (k: keyof QueryFilters, v: unknown) => onChange({ ...value, [k]: v === "" || v === undefined ? undefined : v });
  const numeric = (k: keyof QueryFilters) => (e: React.ChangeEvent<HTMLInputElement>) => set(k, e.target.value ? Number(e.target.value) : undefined);
  const active = Object.values(value).filter((v) => v !== undefined && !(Array.isArray(v) && v.length === 0)).length;

  return (
    <div className="card p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          <SlidersHorizontal size={14} className="text-ink-3" /> Metadata filters
          {active > 0 && <span className="rounded-full bg-accent-soft px-2 text-[11px] text-accent-ink">{active}</span>}
        </div>
        <button onClick={() => onChange({})} className="inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink"><RotateCcw size={11} /> Reset</button>
      </div>
      <div className="space-y-3">
        <div>
          <Label>Neighborhood</Label>
          <Select value={value.neighborhoods?.[0] ?? ""} onChange={(e) => set("neighborhoods", e.target.value ? [e.target.value as Neighborhood] : undefined)}>
            <option value="">Any neighborhood</option>
            {NEIGHBORHOODS.map((n) => <option key={n.code} value={n.code}>{n.name} ({n.code})</option>)}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Built from</Label><Input type="number" placeholder="1900" value={value.minYearBuilt ?? ""} onChange={numeric("minYearBuilt")} /></div>
          <div><Label>Built to</Label><Input type="number" placeholder="2010" value={value.maxYearBuilt ?? ""} onChange={numeric("maxYearBuilt")} /></div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Min bedrooms</Label><Input type="number" placeholder="1" value={value.minBedrooms ?? ""} onChange={numeric("minBedrooms")} /></div>
          <div><Label>Max bedrooms</Label><Input type="number" placeholder="5" value={value.maxBedrooms ?? ""} onChange={numeric("maxBedrooms")} /></div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Min sq ft</Label><Input type="number" placeholder="800" value={value.minGrLivArea ?? ""} onChange={numeric("minGrLivArea")} /></div>
          <div><Label>Max sq ft</Label><Input type="number" placeholder="3000" value={value.maxGrLivArea ?? ""} onChange={numeric("maxGrLivArea")} /></div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Min quality</Label><Input type="number" min={1} max={10} placeholder="1–10" value={value.minQual ?? ""} onChange={numeric("minQual")} /></div>
          <div><Label>Max price</Label><Input type="number" placeholder="$" value={value.maxPrice ?? ""} onChange={numeric("maxPrice")} /></div>
        </div>
      </div>
    </div>
  );
}
