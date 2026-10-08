"use client";
import { motion, useReducedMotion } from "motion/react";
import { Reveal } from "@/components/ui/reveal";

const agents = [
  { name: "Guardrail", role: "Validates input", color: "var(--sage)" },
  { name: "Classifier", role: "Intent & attributes", color: "var(--sky)" },
  { name: "Retriever", role: "Hybrid search", color: "var(--sky)" },
  { name: "Comp Analyst", role: "Prioritize & adjust", color: "var(--accent)" },
  { name: "Pricing Model", role: "ML prediction", color: "var(--accent)" },
  { name: "Risk Analyst", role: "Volatility & coverage", color: "var(--sun)" },
  { name: "Valuer", role: "Ensemble synthesis", color: "var(--accent)" },
  { name: "Judge", role: "Independent validation", color: "var(--sage)" },
];

export function Agents() {
  const reduce = useReducedMotion();
  return (
    <section id="agents" className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="grid items-center gap-14 lg:grid-cols-2">
          <Reveal>
            <div>
              <div className="eyebrow mb-4">Multi-agent collaboration</div>
              <h2 className="display text-[36px] sm:text-[52px] text-ink">
                Specialists that <em>disagree</em> productively.
              </h2>
              <p className="mt-5 text-[16px] leading-relaxed text-ink-2">
                Instead of one prompt doing everything, Valora runs a typed state graph of narrow agents. The comparable analyst
                and the ML pricing model estimate independently; the valuer reconciles them; the judge can send the result back
                for another pass if the two methods diverge or a claim is not grounded in a retrieved record.
              </p>
              <ul className="mt-8 space-y-3 text-[14px] text-ink-2">
                <li className="flex gap-3"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" /> Every hand-off is logged with duration, tool and output, visible in the workspace trace.</li>
                <li className="flex gap-3"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" /> Structured outputs (JSON schemas) between agents, so no agent parses another's prose.</li>
                <li className="flex gap-3"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" /> Model fallback: if the primary LLM times out, the graph degrades to a smaller model and marks the response.</li>
              </ul>
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="card relative overflow-hidden rounded-[22px] p-6">
              <div className="eyebrow mb-5">Execution graph</div>
              <div className="relative">
                <div className="absolute left-[17px] top-3 bottom-3 w-px bg-line" />
                <ol className="space-y-3">
                  {agents.map((a, i) => (
                    <motion.li
                      key={a.name}
                      initial={reduce ? false : { opacity: 0, x: -10 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.08, duration: 0.5 }}
                      className="relative flex items-center gap-4 pl-10"
                    >
                      <span className="absolute left-[11px] h-3.5 w-3.5 rounded-full border-2 border-surface" style={{ background: a.color }} />
                      <div className="flex flex-1 items-center justify-between rounded-xl border border-line-2 bg-paper px-4 py-2.5">
                        <div>
                          <div className="text-[14px] font-medium text-ink">{a.name}</div>
                          <div className="text-[12px] text-ink-3">{a.role}</div>
                        </div>
                        <span className="font-mono text-[11px] text-ink-3">{(40 + i * 210).toString().padStart(4, " ")}ms</span>
                      </div>
                    </motion.li>
                  ))}
                </ol>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
