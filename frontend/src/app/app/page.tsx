"use client";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Shell } from "@/components/app/shell";
import { QueryBar } from "@/components/app/query-bar";
import { FilterPanel } from "@/components/app/filter-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  ValuationCard, AnswerCard, PipelineStatusCard, ComparablesCard, PredictionCard, JudgeCard, RiskCard, ImpactCard, AgentTraceCard, FeedbackCard, type FullResponse,
} from "@/components/app/result-cards";
import { runQuery } from "@/lib/api";
import { describeFilters, hasActiveFilters } from "@/lib/filters";
import type { QueryFilters, QueryResponse } from "@/lib/types";
import { ShieldAlert, Compass } from "lucide-react";

const STAGES = ["Validating input", "Classifying intent", "Hybrid retrieval", "Prioritizing comparables", "Running pricing model", "Assessing risk", "Synthesizing valuation", "Judge review"];

function LoadingState() {
  const [i, setI] = useState(0);
  useEffect(() => { const id = setInterval(() => setI((v) => (v + 1) % STAGES.length), 320); return () => clearInterval(id); }, []);
  return (
    <div className="space-y-4">
      <div className="card flex items-center gap-3 p-4">
        <span className="pulse-dot h-2.5 w-2.5 rounded-full bg-accent" />
        <span className="text-[13.5px] text-ink">{STAGES[i]}…</span>
        <span className="ml-auto font-mono text-[11px] text-ink-3">{i + 1}/{STAGES.length}</span>
      </div>
      <div className="px-1 text-[12px] text-ink-3">
        With LLM agents active, classification, narrative and judging each take a model call; expect 15–45 s through a gateway.
      </div>
      <Skeleton className="h-[260px]" />
      <div className="grid gap-4 lg:grid-cols-2"><Skeleton className="h-[220px]" /><Skeleton className="h-[220px]" /></div>
      <Skeleton className="h-[400px]" />
    </div>
  );
}

export default function ConsolePage() {
  const [filters, setFilters] = useState<QueryFilters>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [history, setHistory] = useState<QueryResponse[]>([]);

  const filtersActive = hasActiveFilters(filters);

  async function submit(text: string) {
    // An empty query box is fine when filters are set: phrase them as the query.
    const q = text.trim() || describeFilters(filters);
    if (!q || loading) return;
    setLoading(true);
    try {
      const r = await runQuery(q, filters);
      setResult(r);
      setHistory((h) => [r, ...h].slice(0, 6));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell title="Valuation console" subtitle="Natural-language property retrieval, valuation and validation">
      <div className="grid gap-6 xl:grid-cols-[300px_1fr]">
        <aside className="space-y-4 xl:sticky xl:top-[88px] xl:self-start">
          <FilterPanel value={filters} onChange={setFilters} onApply={() => submit("")} loading={loading} />
          {history.length > 0 && (
            <div className="card p-4">
              <div className="mb-2 text-[13px] font-semibold text-ink">Recent queries</div>
              <ul className="space-y-1">
                {history.map((h) => (
                  <li key={h.requestId}>
                    <button onClick={() => setResult(h)} className="w-full truncate rounded-lg px-2 py-1.5 text-left text-[12.5px] text-ink-2 hover:bg-surface-2 hover:text-ink">{h.query}</button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>

        <div className="min-w-0 space-y-5">
          <QueryBar onSubmit={submit} loading={loading} filtersActive={filtersActive} />

          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><LoadingState /></motion.div>
            ) : result ? (
              <motion.div key={result.requestId} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }} className="space-y-5">
                <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-3">
                  <span>Results for</span><span className="text-ink">“{result.query}”</span>
                  {result.mode === "demo" && <Badge tone="warning">demo data</Badge>}
                  {result.engine && <Badge tone={result.engine === "llm" ? "sage" : result.engine === "llm-degraded" ? "warning" : "sky"}>{result.engine === "llm" ? "LLM agents" : result.engine === "llm-degraded" ? "LLM · degraded" : "rules engine"}</Badge>}
                  <Badge tone="outline" className="font-mono">{result.requestId}</Badge>
                </div>

                {!result.guardrails.passed || !result.valuation || !result.prediction || !result.judge || !result.risk || !result.classification ? (
                  <div className="card flex items-start gap-3 border-critical/40 p-5">
                    <ShieldAlert size={20} className="mt-0.5 text-critical" />
                    <div>
                      <div className="text-[15px] font-semibold text-ink">Request blocked by input guardrails</div>
                      <p className="mt-1 text-[13.5px] text-ink-2">The query was rejected before any model call. Rephrase it as a property description or valuation question.</p>
                    </div>
                  </div>
                ) : (
                  <>
                    <ValuationCard r={result as FullResponse} />
                    <AnswerCard r={result as FullResponse} />
                    <div className="grid gap-5 lg:grid-cols-2">
                      <JudgeCard r={result as FullResponse} />
                      <RiskCard r={result as FullResponse} />
                    </div>
                    <ComparablesCard r={result as FullResponse} />
                    <PredictionCard r={result as FullResponse} />
                    <div className="grid gap-5 lg:grid-cols-2">
                      <ImpactCard r={result as FullResponse} />
                      <div className="space-y-5">
                        <FeedbackCard r={result} />
                      </div>
                    </div>
                  </>
                )}
                <PipelineStatusCard r={result} />
                <AgentTraceCard r={result} />
              </motion.div>
            ) : (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card flex flex-col items-center justify-center px-6 py-20 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft text-accent-ink"><Compass size={22} /></div>
                <h2 className="display mt-5 text-[30px] text-ink">Describe a property to begin.</h2>
                <p className="mt-2 max-w-md text-[14px] text-ink-2">Mention the neighborhood, size, age, rooms or quality. Use the filters on the left to constrain the comparable pool, or pick a suggested query above.</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </Shell>
  );
}
