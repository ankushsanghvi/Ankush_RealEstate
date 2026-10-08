import { NEIGHBORHOODS } from "@/lib/mock";
import type { QueryFilters } from "@/lib/types";

const fmt = (n: number) => n.toLocaleString("en-US");

function range(min: number | undefined, max: number | undefined, unit: string, single?: string): string | null {
  if (min !== undefined && max !== undefined) return `${fmt(min)}–${fmt(max)} ${unit}`;
  if (min !== undefined) return `at least ${fmt(min)} ${single ?? unit}`;
  if (max !== undefined) return `at most ${fmt(max)} ${single ?? unit}`;
  return null;
}

/** True when at least one filter carries a value. */
export function hasActiveFilters(f: QueryFilters): boolean {
  return Object.values(f).some((v) => v !== undefined && !(Array.isArray(v) && v.length === 0));
}

/**
 * Turn the metadata filters into a natural-language query so the console can be
 * submitted without typing anything. The sentence always contains real-estate
 * vocabulary ("properties", "built", "bedrooms", "sq ft") so it passes the
 * backend's length and domain guardrails.
 */
export function describeFilters(f: QueryFilters): string {
  if (!hasActiveFilters(f)) return "";
  const parts: string[] = [];
  const hood = f.neighborhoods?.[0];
  if (hood) parts.push(`in ${NEIGHBORHOODS.find((n) => n.code === hood)?.name ?? hood}`);

  if (f.minYearBuilt !== undefined && f.maxYearBuilt !== undefined) parts.push(`built between ${f.minYearBuilt} and ${f.maxYearBuilt}`);
  else if (f.minYearBuilt !== undefined) parts.push(`built in ${f.minYearBuilt} or later`);
  else if (f.maxYearBuilt !== undefined) parts.push(`built in ${f.maxYearBuilt} or earlier`);

  const beds = range(f.minBedrooms, f.maxBedrooms, "bedrooms");
  if (beds) parts.push(`with ${beds}`);
  const area = range(f.minGrLivArea, f.maxGrLivArea, "sq ft");
  if (area) parts.push(area);
  if (f.minQual !== undefined) parts.push(`quality ${f.minQual} or higher`);
  if (f.maxPrice !== undefined) parts.push(`priced under $${fmt(f.maxPrice)}`);

  return `Find comparable properties ${parts.join(", ")} and estimate their value.`;
}
