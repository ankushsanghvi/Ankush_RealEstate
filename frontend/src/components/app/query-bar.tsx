"use client";
import { useState } from "react";
import { ArrowUp, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "3-bedroom in College Creek, 1,650 sq ft, built 1998, quality 7 — what is it worth?",
  "Similar sales to a 4-bed Northridge Heights home with a 3-car garage",
  "Why would a 2,000 sq ft Somerset house be worth more than one in Gilbert?",
  "Estimate a 1950s Old Town bungalow, 1,100 sq ft, 2 bedrooms, quality 5",
];

export function QueryBar({ onSubmit, loading, initial = "" }: { onSubmit: (q: string) => void; loading: boolean; initial?: string }) {
  const [value, setValue] = useState(initial);
  const submit = () => { if (value.trim() && !loading) onSubmit(value.trim()); };
  return (
    <div>
      <div className={cn("card flex items-end gap-2 rounded-2xl p-2 pl-4 transition-shadow focus-within:shadow-md", loading && "opacity-80")}>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
          rows={2}
          placeholder="Describe the property or ask a valuation question in plain language…"
          className="max-h-40 min-h-[52px] flex-1 resize-none bg-transparent py-2 text-[15px] leading-relaxed text-ink placeholder:text-ink-3 focus:outline-none"
        />
        <button
          onClick={submit}
          disabled={loading || !value.trim()}
          aria-label="Run query"
          className="mb-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-ink text-paper transition-opacity disabled:opacity-30"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => { setValue(s); onSubmit(s); }}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:border-accent hover:text-ink"
          >
            <Sparkles size={11} className="text-accent" /> {s.length > 58 ? s.slice(0, 58) + "…" : s}
          </button>
        ))}
      </div>
    </div>
  );
}
