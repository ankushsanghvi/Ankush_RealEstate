"use client";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, Sparkles, ShieldCheck, Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Meter } from "@/components/ui/meter";

const QUERIES = [
  "3-bed home in College Creek, ~1,650 sq ft, built 1998, 2-car garage — what is it worth?",
  "Find comparable sales for a 4-bedroom in Northridge Heights with quality 8",
  "Why does this Somerset house sell for 20% more than a similar one in Gilbert?",
];

function useTypewriter(lines: string[], speed = 28, pause = 2200) {
  const [i, setI] = useState(0);
  const [text, setText] = useState("");
  const [deleting, setDeleting] = useState(false);
  useEffect(() => {
    const full = lines[i];
    let t: ReturnType<typeof setTimeout>;
    if (!deleting && text.length < full.length) t = setTimeout(() => setText(full.slice(0, text.length + 1)), speed);
    else if (!deleting && text.length === full.length) t = setTimeout(() => setDeleting(true), pause);
    else if (deleting && text.length > 0) t = setTimeout(() => setText(full.slice(0, text.length - 1)), 10);
    else { setDeleting(false); setI((i + 1) % lines.length); }
    return () => clearTimeout(t);
  }, [text, deleting, i, lines, speed, pause]);
  return text;
}

const ease = [0.22, 1, 0.36, 1] as const;

export function Hero() {
  const text = useTypewriter(QUERIES);
  const reduce = useReducedMotion();
  const fade = (d: number) => ({
    initial: reduce ? false : { opacity: 0, y: 24 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.9, delay: d, ease },
  });

  return (
    <section className="relative overflow-hidden pt-36 pb-20 sm:pt-44 sm:pb-28">

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        <div className="grid items-center gap-14 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <motion.div {...fade(0)}>
              <Badge tone="accent" className="mb-6">
                <Sparkles size={12} /> Built on the Ames Housing dataset · 2,930 historical sales
              </Badge>
            </motion.div>
            <motion.h1 {...fade(0.08)} className="display text-[44px] sm:text-[64px] lg:text-[76px] text-ink">
              Property valuation,
              <br />
              <em>grounded</em> in evidence.
            </motion.h1>
            <motion.p {...fade(0.18)} className="mt-6 max-w-xl text-[17px] leading-relaxed text-ink-2 sm:text-lg">
              Ask in plain language. Valora retrieves the most relevant historical sales with hybrid search,
              prioritizes true comparables, runs a multi-agent valuation and has an independent judge validate every number before you see it.
            </motion.p>
            <motion.div {...fade(0.28)} className="mt-8 flex flex-wrap items-center gap-3">
              <Button href="/app" size="lg">
                Start a valuation <ArrowRight size={16} />
              </Button>
              <Button href="#how" size="lg" variant="outline">
                See how it works
              </Button>
            </motion.div>
            <motion.div {...fade(0.4)} className="mt-10 flex flex-wrap gap-x-7 gap-y-3 text-[13px] text-ink-3">
              <span className="inline-flex items-center gap-2"><ShieldCheck size={15} className="text-accent" /> Input guardrails on every request</span>
              <span className="inline-flex items-center gap-2"><Scale size={15} className="text-accent" /> LLM-as-judge validation</span>
              <span className="inline-flex items-center gap-2"><Sparkles size={15} className="text-accent" /> DeepEval scored nightly</span>
            </motion.div>
          </div>

          {/* Live preview card */}
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 40, rotate: 1.5 }}
            animate={{ opacity: 1, y: 0, rotate: 0 }}
            transition={{ duration: 1.1, delay: 0.25, ease }}
            className="relative"
          >
            {/* arch backdrop */}
            <div aria-hidden className="absolute -inset-x-6 -top-10 bottom-[-40px] hidden rounded-t-full bg-sky-soft lg:block" />
            <div className="card relative overflow-hidden rounded-[22px] p-5 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="eyebrow">Live query</span>
                <span className="inline-flex items-center gap-2 text-[12px] text-ink-3">
                  <span className="pulse-dot h-2 w-2 rounded-full bg-sage" /> pipeline ready
                </span>
              </div>
              <div className="mt-3 min-h-[72px] rounded-xl border border-line bg-paper px-4 py-3 text-[14px] leading-relaxed text-ink">
                <span className="caret">{text}</span>
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-surface-2 p-4">
                  <div className="text-[12px] text-ink-3">Estimated value</div>
                  <div className="mt-1 font-serif text-[34px] leading-none tracking-tight text-ink">$214,500</div>
                  <div className="mt-2 text-[12px] text-ink-3 tabular">$203,000 – $226,000</div>
                </div>
                <div className="rounded-xl bg-surface-2 p-4">
                  <div className="text-[12px] text-ink-3">Confidence</div>
                  <div className="mt-1 font-serif text-[34px] leading-none tracking-tight text-ink">87%</div>
                  <Meter value={0.87} color="var(--sage)" className="mt-3 bg-paper" />
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {[
                  { id: "AMES-1214", nb: "College Creek", price: "$218,000", score: 0.94 },
                  { id: "AMES-1087", nb: "College Creek", price: "$209,500", score: 0.91 },
                  { id: "AMES-1402", nb: "Gilbert", price: "$212,000", score: 0.83 },
                ].map((c, i) => (
                  <motion.div
                    key={c.id}
                    initial={reduce ? false : { opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.9 + i * 0.12, duration: 0.6, ease }}
                    className="flex items-center justify-between rounded-lg border border-line-2 px-3 py-2 text-[13px]"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[12px] text-ink-3">{c.id}</span>
                      <span className="text-ink">{c.nb}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="tabular text-ink">{c.price}</span>
                      <span className="w-14"><Meter value={c.score} /></span>
                    </div>
                  </motion.div>
                ))}
              </div>

              <div className="mt-4 flex items-center justify-between rounded-lg bg-sage-soft px-3 py-2 text-[12.5px] text-[color:var(--sage)]">
                <span className="inline-flex items-center gap-2"><ShieldCheck size={14} /> Judge: approved · 5/5 criteria</span>
                <span className="font-mono">1.8s</span>
              </div>
            </div>

            {/* floating chips */}
            <motion.div
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.3, duration: 0.7, ease }}
              className="absolute -left-6 top-14 hidden rounded-full border border-line bg-surface px-3 py-1.5 text-[12px] shadow-md lg:block"
            >
              <span className="text-ink-3">Hybrid</span> <span className="text-ink">BM25 + dense</span>
            </motion.div>
            <motion.div
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.5, duration: 0.7, ease }}
              className="absolute -right-4 bottom-24 hidden rounded-full border border-line bg-surface px-3 py-1.5 text-[12px] shadow-md lg:block"
            >
              <span className="text-ink-3">Risk</span> <span className="text-ink">low · 28/100</span>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
