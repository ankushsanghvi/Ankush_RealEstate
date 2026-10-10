"use client";
import { useEffect, useState } from "react";
import { Shell } from "@/components/app/shell";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Meter, Stat } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { EvalHistoryChart } from "@/components/app/charts";
import { getEvaluation } from "@/lib/api";
import type { EvalSummary } from "@/lib/types";
import { pct, num, cn } from "@/lib/utils";
import { Check, X, ThumbsUp, ThumbsDown, PenLine } from "lucide-react";

export default function EvaluationPage() {
  const [ev, setEv] = useState<EvalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getEvaluation().then(setEv, (e) => setError(e instanceof Error ? e.message : "Request failed")); }, []);

  return (
    <Shell title="Evaluation & feedback" subtitle="DeepEval quality suite, judge agreement and the human feedback loop">
      {error ? (
        <Card><CardBody className="pt-5 text-[13.5px] text-ink-2"><span className="font-semibold text-ink">Evaluation results are unavailable.</span> {error}. Metrics are only shown when they come from the backend.</CardBody></Card>
      ) : !ev ? (
        <div className="grid gap-5 lg:grid-cols-3"><Skeleton className="h-40" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Card><CardBody className="pt-5"><Stat label="Golden-set cases" value={num(ev.cases)} hint={`run ${ev.runId}`} /></CardBody></Card>
            <Card><CardBody className="pt-5"><Stat label="Judge ↔ outcome agreement" value={pct(ev.judgeAgreement)} hint="approved ⇔ hold-out error < 15%" /></CardBody></Card>
            <Card><CardBody className="pt-5"><Stat label="Latency p50 / p95" value={<span className="tabular">{(ev.latencyP50 / 1000).toFixed(2)}s <span className="text-ink-3">/</span> {(ev.latencyP95 / 1000).toFixed(2)}s</span>} hint="end-to-end, cached embeddings" /></CardBody></Card>
            <Card><CardBody className="pt-5"><Stat label="Metrics passing threshold" value={`${ev.metrics.filter((m) => (m.name === "Hallucination" || m.name === "Valuation MAPE" ? m.score <= m.threshold : m.score >= m.threshold)).length}/${ev.metrics.length}`} hint="gates CI deploys" /></CardBody></Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <Card>
              <CardHeader eyebrow={ev.source === "deepeval" ? "DeepEval metrics (LLM-graded)" : ev.source === "none" ? "No evaluation run yet" : "Built-in evaluation metrics"} title="Latest run" subtitle={ev.ranAt ? new Date(ev.ranAt).toLocaleString() : "Run evals/run_eval.py or evals/run_deepeval.py"} />
              <CardBody className="space-y-4">
                {ev.metrics.map((m) => {
                  const lowerIsBetter = m.name === "Hallucination" || m.name === "Valuation MAPE";
                  const ok = lowerIsBetter ? m.score <= m.threshold : m.score >= m.threshold;
                  return (
                    <div key={m.name}>
                      <div className="mb-1.5 flex items-center justify-between text-[13px]">
                        <span className="flex items-center gap-2 text-ink">{ok ? <Check size={13} className="text-good" /> : <X size={13} className="text-critical" />}{m.name}</span>
                        <span className="tabular text-ink-2">{(m.score * 100).toFixed(1)}% <span className="text-ink-3">· threshold {lowerIsBetter ? "≤" : "≥"} {(m.threshold * 100).toFixed(0)}% · pass rate {pct(m.passRate)}</span></span>
                      </div>
                      <Meter value={lowerIsBetter ? 1 - m.score : m.score} color={ok ? "var(--series-1)" : "var(--status-serious)"} />
                    </div>
                  );
                })}
              </CardBody>
            </Card>
            <Card>
              <CardHeader eyebrow="Trend" title="Quality across recent runs" subtitle="One point per evaluation run; corrected feedback joins the golden set automatically" />
              <CardBody><EvalHistoryChart data={ev.history} /></CardBody>
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader eyebrow="Feedback loop" title="Human signals collected" />
              <CardBody className="space-y-3">
                {[
                  { icon: ThumbsUp, label: "Helpful", v: ev.feedback.positive, col: "var(--sage)" },
                  { icon: ThumbsDown, label: "Off", v: ev.feedback.negative, col: "var(--status-serious)" },
                  { icon: PenLine, label: "Corrected values", v: ev.feedback.corrected, col: "var(--sky)" },
                ].map((f) => (
                  <div key={f.label} className="flex items-center gap-3 text-[13px]">
                    <f.icon size={14} className="text-ink-3" />
                    <span className="w-32 text-ink-2">{f.label}</span>
                    <span className="flex-1"><Meter value={f.v / (ev.feedback.positive + 1)} color={f.col} /></span>
                    <span className="w-10 text-right tabular text-ink">{f.v}</span>
                  </div>
                ))}
                <p className="pt-2 text-[12px] leading-relaxed text-ink-3">Negative ratings open a review item; corrected values become labelled cases for the next eval run and retrain the comparable-prioritization weights weekly.</p>
              </CardBody>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader eyebrow="How evaluation works" title="Three layers of quality control" />
              <CardBody>
                <div className="grid gap-4 sm:grid-cols-3">
                  {[
                    { t: "Offline · golden set + DeepEval", d: `${ev.cases || 60} golden cases: hold-out valuations from real sales, intents and guardrails. The built-in runner scores precision/recall, MAPE, range coverage and groundedness in CI without a key; DeepEval adds LLM-graded faithfulness, relevancy and hallucination.`, tone: "sky" as const },
                    { t: "Online · LLM-as-judge", d: "Every production response is scored against five criteria before it is returned. Flagged responses carry a warning; rejected ones are withheld.", tone: "accent" as const },
                    { t: "Human · feedback loop", d: "Ratings and corrections from reviewers are stored with the request id, replayed into the golden set and used to tune reranker weights.", tone: "sage" as const },
                  ].map((l) => (
                    <div key={l.t} className={cn("rounded-xl border border-line-2 bg-paper p-4")}>
                      <Badge tone={l.tone} className="mb-2">{l.t}</Badge>
                      <p className="text-[12.5px] leading-relaxed text-ink-2">{l.d}</p>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </Shell>
  );
}
