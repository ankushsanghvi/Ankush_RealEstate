"use client";
import { useState } from "react";
import { motion } from "motion/react";
import {
  ShieldCheck, ShieldAlert, Gavel, Check, X, AlertTriangle, ChevronDown, ChevronUp, ThumbsUp, ThumbsDown, Send, Loader2, Tag, Clock, Cpu,
} from "lucide-react";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Meter, Stat } from "@/components/ui/meter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { sendFeedback } from "@/lib/api";
import { usd, pct, cn, num } from "@/lib/utils";
import type { QueryResponse, Comparable } from "@/lib/types";

/** A response whose pipeline ran to completion (guardrails passed). */
export type FullResponse = QueryResponse & {
  classification: NonNullable<QueryResponse["classification"]>;
  valuation: NonNullable<QueryResponse["valuation"]>;
  prediction: NonNullable<QueryResponse["prediction"]>;
  judge: NonNullable<QueryResponse["judge"]>;
  risk: NonNullable<QueryResponse["risk"]>;
};
import { NEIGHBORHOODS } from "@/lib/mock";
import { ContributionChart, ComparableRangeChart } from "./charts";

const nbName = (c: string) => NEIGHBORHOODS.find((n) => n.code === c)?.name ?? c;

/* ---------------- Valuation hero ---------------- */
export function ValuationCard({ r }: { r: FullResponse }) {
  const v = r.valuation;
  return (
    <Card className="overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-[1.2fr_1fr]">
        <div className="p-6">
          <div className="flex items-center gap-2">
            <span className="eyebrow">Valuation recommendation</span>
            <Badge tone="neutral" className="font-mono text-[11px]">{v.method}</Badge>
          </div>
          <div className="mt-3 font-serif text-[56px] leading-none tracking-tight text-ink sm:text-[68px]">{usd(v.estimate)}</div>
          <div className="mt-2 text-[14px] text-ink-2 tabular">
            Range <span className="text-ink">{usd(v.low)}</span> – <span className="text-ink">{usd(v.high)}</span>
            <span className="mx-2 text-ink-3">·</span>
            <span className="text-ink">{usd(v.pricePerSqft)}</span>/sq ft
          </div>
          <div className="mt-5 flex items-center gap-4">
            <div className="flex-1">
              <div className="mb-1.5 flex justify-between text-[12px]"><span className="text-ink-3">Confidence</span><span className="tabular text-ink">{pct(v.confidence)}</span></div>
              <Meter value={v.confidence} color={v.confidence > 0.75 ? "var(--sage)" : v.confidence > 0.55 ? "var(--sun)" : "var(--status-serious)"} />
            </div>
          </div>
          <p className="mt-5 text-[13.5px] leading-relaxed text-ink-2">{v.narrative}</p>
        </div>
        <div className="border-t border-line bg-paper p-6 lg:border-l lg:border-t-0">
          <div className="eyebrow mb-3">Where the comparables land</div>
          <ComparableRangeChart comparables={r.comparables} estimate={v.estimate} low={v.low} high={v.high} />
          <p className="mt-3 text-[12px] text-ink-3">Adjusted sale price of each prioritized comparable. Shaded band is the recommended range.</p>
        </div>
      </div>
    </Card>
  );
}

/* ---------------- Answer narrative ---------------- */
export function AnswerCard({ r }: { r: FullResponse }) {
  return (
    <Card>
      <CardHeader eyebrow="Synthesized answer" title="What the assistant concluded" action={<Badge tone="outline" className="font-mono"><Clock size={11} /> {(r.latencyMs / 1000).toFixed(1)}s</Badge>} />
      <CardBody>
        <p className="text-[15px] leading-relaxed text-ink">{r.answer}</p>
      </CardBody>
    </Card>
  );
}

/* ---------------- Classification + guardrails ---------------- */
export function PipelineStatusCard({ r }: { r: QueryResponse }) {
  const c = r.classification;
  const g = r.guardrails;
  const attrs = c ? Object.entries(c.extractedAttributes).filter(([, v]) => v !== undefined && v !== null) : [];
  return (
    <Card>
      <CardHeader eyebrow="Classification & guardrails" title={c ? <span className="flex items-center gap-2">Intent: <Badge tone="sky">{c.intent.replace("_", " ")}</Badge><span className="text-ink-3 text-[12px] font-normal tabular">{pct(c.confidence)} conf.</span></span> : "Blocked before classification"} />
      <CardBody className="space-y-4">
        {c && <p className="text-[13px] leading-relaxed text-ink-2">{c.rationale}</p>}
        <div className="flex flex-wrap gap-1.5">
          {attrs.map(([k, v]) => (
            <Badge key={k} tone="neutral"><Tag size={10} className="text-ink-3" /><span className="text-ink-3">{k}</span> <span className="tabular">{k === "neighborhood" ? nbName(String(v)) : String(v)}</span></Badge>
          ))}
        </div>
        <div className="rounded-xl border border-line-2 bg-paper p-3">
          <div className="mb-2 flex items-center gap-2 text-[12.5px] font-medium text-ink">
            {g.passed ? <ShieldCheck size={14} className="text-good" /> : <ShieldAlert size={14} className="text-critical" />}
            Input guardrails {g.passed ? "passed" : "blocked"}
          </div>
          <ul className="space-y-1.5">
            {g.checks.map((ch) => (
              <li key={ch.name} className="flex items-start gap-2 text-[12.5px]">
                {ch.status === "pass" ? <Check size={13} className="mt-0.5 text-good" /> : ch.status === "warn" ? <AlertTriangle size={13} className="mt-0.5 text-warning" /> : <X size={13} className="mt-0.5 text-critical" />}
                <span className="text-ink">{ch.name}</span>
                <span className="text-ink-3">· {ch.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </CardBody>
    </Card>
  );
}

/* ---------------- Comparables ---------------- */
function ComparableRow({ c, rank }: { c: Comparable; rank: number }) {
  const [open, setOpen] = useState(rank === 1);
  const p = c.property;
  const net = c.adjustments.reduce((s, a) => s + a.amount, 0);
  return (
    <motion.div layout className="rounded-xl border border-line-2 bg-surface transition-colors hover:border-line">
      <button onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-4 px-4 py-3 text-left">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-2 font-mono text-[11px] text-ink-2">{rank}</span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-mono text-[12px] text-ink-3">{p.id}</span>
            <span className="text-[14px] font-medium text-ink">{nbName(p.neighborhood)}</span>
            <span className="text-[12.5px] text-ink-3">{p.bedroomAbvGr} bd · {p.fullBath} ba · {num(p.grLivArea)} sq ft · built {p.yearBuilt} · Q{p.overallQual}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {c.priorityReasons.map((rsn) => <span key={rsn} className="rounded-md bg-sage-soft px-1.5 py-0.5 text-[11px] text-[color:var(--sage)]">{rsn}</span>)}
          </div>
        </div>
        <div className="hidden shrink-0 text-right sm:block">
          <div className="tabular text-[14px] font-medium text-ink">{usd(p.salePrice)}</div>
          <div className="tabular text-[11.5px] text-ink-3">adj. {usd(c.adjustedPrice)}</div>
        </div>
        <div className="hidden w-24 shrink-0 md:block">
          <div className="mb-1 flex justify-between text-[10.5px] text-ink-3"><span>priority</span><span className="tabular">{(c.priorityScore * 100).toFixed(0)}</span></div>
          <Meter value={c.priorityScore} color="var(--accent)" />
        </div>
        {open ? <ChevronUp size={15} className="text-ink-3" /> : <ChevronDown size={15} className="text-ink-3" />}
      </button>
      {open && (
        <div className="grid gap-4 border-t border-line-2 px-4 py-4 sm:grid-cols-[1fr_1fr_1.2fr]">
          <div>
            <div className="eyebrow mb-2">Retrieval scores</div>
            {[
              { l: "Semantic (cosine)", v: c.semanticScore, col: "var(--series-1)" },
              { l: "Keyword (BM25)", v: c.keywordScore, col: "var(--series-2)" },
              { l: "Hybrid (RRF)", v: c.hybridScore, col: "var(--series-3)" },
            ].map((s) => (
              <div key={s.l} className="mb-2">
                <div className="mb-1 flex justify-between text-[12px]"><span className="text-ink-2">{s.l}</span><span className="tabular text-ink">{s.v.toFixed(2)}</span></div>
                <Meter value={s.v} color={s.col} />
              </div>
            ))}
          </div>
          <div>
            <div className="eyebrow mb-2">Adjustments to subject</div>
            <ul className="space-y-1 text-[12.5px]">
              {c.adjustments.map((a) => (
                <li key={a.label} className="flex justify-between"><span className="text-ink-2">{a.label}</span><span className={cn("tabular", a.amount > 0 ? "text-[color:var(--delta-good-text)]" : "text-critical")}>{a.amount > 0 ? "+" : ""}{usd(a.amount)}</span></li>
              ))}
              <li className="flex justify-between border-t border-line-2 pt-1 font-medium"><span className="text-ink">Net</span><span className="tabular text-ink">{net > 0 ? "+" : ""}{usd(net)}</span></li>
            </ul>
          </div>
          <div>
            <div className="eyebrow mb-2">Record</div>
            <p className="text-[12.5px] leading-relaxed text-ink-2">{p.summary}</p>
          </div>
        </div>
      )}
    </motion.div>
  );
}

export function ComparablesCard({ r }: { r: FullResponse }) {
  return (
    <Card>
      <CardHeader eyebrow="Comparable-property prioritization" title={`${r.comparables.length} prioritized comparables`} subtitle="Hybrid retrieval → metadata filter → reranked by neighborhood, size, age and quality proximity" />
      <CardBody className="space-y-2">
        {r.comparables.map((c, i) => <ComparableRow key={c.property.id} c={c} rank={i + 1} />)}
      </CardBody>
    </Card>
  );
}

/* ---------------- ML prediction ---------------- */
export function PredictionCard({ r }: { r: FullResponse }) {
  const p = r.prediction;
  const delta = (p.prediction - r.valuation.estimate) / r.valuation.estimate;
  return (
    <Card>
      <CardHeader eyebrow="Price prediction" title="Gradient-boosted model" subtitle={p.model} action={<Badge tone="outline" className="font-mono"><Cpu size={11} /> R² {p.r2.toFixed(2)} · MAPE {pct(p.mape, 1)}</Badge>} />
      <CardBody>
        <div className="grid grid-cols-3 gap-4">
          <Stat label="Prediction" value={<span className="tabular">{usd(p.prediction)}</span>} />
          <Stat label="90% interval" value={<span className="tabular text-[16px]">{usd(p.low)} – {usd(p.high)}</span>} />
          <Stat label="vs. comparables" value={<span className={cn("tabular", Math.abs(delta) < 0.05 ? "text-[color:var(--delta-good-text)]" : "text-warning")}>{delta > 0 ? "+" : ""}{pct(delta, 1)}</span>} hint={Math.abs(delta) < 0.05 ? "methods agree" : "methods diverge"} />
        </div>
        <div className="mt-5">
          <div className="eyebrow mb-2">Feature contributions to this prediction</div>
          <ContributionChart data={p.featureContributions} />
        </div>
      </CardBody>
    </Card>
  );
}

/* ---------------- Judge ---------------- */
export function JudgeCard({ r }: { r: FullResponse }) {
  const j = r.judge;
  const tone = j.verdict === "approved" ? "good" : j.verdict === "flagged" ? "warning" : "critical";
  return (
    <Card className={cn(j.verdict === "rejected" && "border-critical/40")}>
      <CardHeader eyebrow="LLM-as-judge validation" title={<span className="flex items-center gap-2"><Gavel size={15} className="text-ink-3" /> Verdict <Badge tone={tone}>{j.verdict}</Badge></span>} action={<span className="font-serif text-[28px] leading-none text-ink tabular">{Math.round(j.score * 100)}<span className="text-[14px] text-ink-3">/100</span></span>} />
      <CardBody>
        <ul className="space-y-2">
          {j.criteria.map((c) => (
            <li key={c.name} className="flex items-start gap-2 text-[13px]">
              {c.pass ? <Check size={14} className="mt-0.5 shrink-0 text-good" /> : <X size={14} className="mt-0.5 shrink-0 text-critical" />}
              <div><span className="text-ink">{c.name}</span><span className="text-ink-3"> · {c.note}</span></div>
            </li>
          ))}
        </ul>
        <p className="mt-4 rounded-xl bg-paper p-3 text-[13px] leading-relaxed text-ink-2">{j.summary}</p>
      </CardBody>
    </Card>
  );
}

/* ---------------- Risk ---------------- */
export function RiskCard({ r }: { r: FullResponse }) {
  const k = r.risk;
  const tone = k.level === "low" ? "good" : k.level === "moderate" ? "warning" : "critical";
  const color = k.level === "low" ? "var(--sage)" : k.level === "moderate" ? "var(--sun)" : "var(--status-serious)";
  return (
    <Card>
      <CardHeader eyebrow="Value-risk prediction" title={<span className="flex items-center gap-2">Risk <Badge tone={tone}>{k.level}</Badge></span>} action={<span className="font-serif text-[28px] leading-none text-ink tabular">{k.score}<span className="text-[14px] text-ink-3">/100</span></span>} />
      <CardBody>
        <Meter value={k.score / 100} color={color} className="mb-4" />
        <ul className="space-y-2">
          {k.drivers.map((d) => (
            <li key={d.label} className="flex items-center gap-3 text-[13px]">
              <span className="w-40 shrink-0 text-ink-2">{d.label}</span>
              <span className="flex-1"><Meter value={d.weight / 40} color={d.direction === "up" ? "var(--status-serious)" : "var(--sage)"} /></span>
              <span className="w-14 text-right tabular text-ink-3">{d.direction === "up" ? "+" : "−"}{d.weight}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 grid grid-cols-2 gap-3 border-t border-line-2 pt-4">
          <Stat label="Neighborhood $/sq ft dispersion" value={<span className="tabular text-[18px]">{pct(k.volatility12m, 1)}</span>} hint="coefficient of variation" />
          <Stat label="Sales in neighborhood" value={<span className="tabular text-[18px]">{num(k.neighborhoodSales)}</span>} hint="records in dataset" />
        </div>
      </CardBody>
    </Card>
  );
}

/* ---------------- Impact analysis ---------------- */
export function ImpactCard({ r }: { r: FullResponse }) {
  const max = Math.max(...r.impact.map((i) => i.elasticity));
  return (
    <Card>
      <CardHeader eyebrow="Feature & location impact" title="What moves price in this market" subtitle="Elasticities estimated on the full dataset, interpreted for the subject" />
      <CardBody className="space-y-3">
        {r.impact.map((i) => (
          <div key={i.feature}>
            <div className="mb-1 flex items-center justify-between text-[13px]"><span className="font-medium text-ink">{i.feature}</span><span className="tabular text-ink-3">{pct(i.elasticity, 1)}</span></div>
            <Meter value={i.elasticity / max} color="var(--series-1)" />
            <p className="mt-1 text-[12px] leading-relaxed text-ink-3">{i.description}</p>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

/* ---------------- Agent trace ---------------- */
export function AgentTraceCard({ r }: { r: QueryResponse }) {
  const total = r.agentTrace.reduce((s, a) => s + a.durationMs, 0);
  return (
    <Card>
      <CardHeader eyebrow="Multi-agent trace" title={`${r.agentTrace.length} agents · ${(total / 1000).toFixed(2)}s`} action={<Badge tone="outline" className="font-mono">{r.requestId}</Badge>} />
      <CardBody>
        <ol className="relative space-y-0">
          <div className="absolute left-[7px] top-2 bottom-2 w-px bg-line" />
          {r.agentTrace.map((a, i) => (
            <motion.li key={a.agent} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="relative flex gap-4 py-2 pl-7">
              <span className={cn("absolute left-0 top-3.5 h-[15px] w-[15px] rounded-full border-[3px] border-surface", a.status === "done" ? "bg-sage" : a.status === "error" ? "bg-critical" : "bg-ink-3")} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 text-[13px]">
                  <span className="font-medium text-ink">{a.agent}</span>
                  <span className="text-ink-3">{a.role}</span>
                  {a.tool && <span className="rounded bg-surface-2 px-1.5 font-mono text-[10.5px] text-ink-3">{a.tool}</span>}
                </div>
                <div className="mt-0.5 font-mono text-[12px] text-ink-2">{a.output}</div>
              </div>
              <span className="shrink-0 font-mono text-[11.5px] text-ink-3 tabular">{a.durationMs}ms</span>
            </motion.li>
          ))}
        </ol>
      </CardBody>
    </Card>
  );
}

/* ---------------- Feedback ---------------- */
export function FeedbackCard({ r }: { r: QueryResponse }) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [corrected, setCorrected] = useState("");
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [mode, setMode] = useState<"live" | "demo" | null>(null);

  async function submit() {
    if (!rating) return;
    setState("sending");
    const res = await sendFeedback({ requestId: r.requestId, rating, correctedValue: corrected ? Number(corrected) : undefined, comment: comment || undefined });
    setMode(res.mode);
    setState("sent");
  }

  if (state === "sent") {
    return (
      <Card className="border-sage/40 bg-sage-soft/40">
        <CardBody className="pt-5">
          <div className="flex items-center gap-2 text-[14px] font-medium text-ink"><Check size={16} className="text-good" /> Thanks, feedback recorded{mode === "demo" ? " (demo)" : ""}.</div>
          <p className="mt-1 text-[12.5px] text-ink-2">It joins the evaluation set and nudges the comparable-prioritization weights on the next retraining run.</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader eyebrow="Feedback loop" title="Was this valuation useful?" subtitle="Corrections feed the golden set and reranker weights" />
      <CardBody className="space-y-3">
        <div className="flex gap-2">
          <button onClick={() => setRating("up")} className={cn("inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-lg border text-[13px] transition-colors", rating === "up" ? "border-sage bg-sage-soft text-ink" : "border-line text-ink-2 hover:bg-surface-2")}><ThumbsUp size={14} /> Helpful</button>
          <button onClick={() => setRating("down")} className={cn("inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-lg border text-[13px] transition-colors", rating === "down" ? "border-serious bg-[color:var(--serious-soft)] text-ink" : "border-line text-ink-2 hover:bg-surface-2")}><ThumbsDown size={14} /> Off</button>
        </div>
        {rating && (
          <>
            <Input type="number" placeholder="Corrected value, if known (USD)" value={corrected} onChange={(e) => setCorrected(e.target.value)} />
            <Input placeholder="What was wrong or missing?" value={comment} onChange={(e) => setComment(e.target.value)} />
            <Button onClick={submit} disabled={state === "sending"} size="sm" className="w-full">
              {state === "sending" ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Submit feedback
            </Button>
          </>
        )}
      </CardBody>
    </Card>
  );
}
