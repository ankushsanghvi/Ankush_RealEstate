"use client";
import { motion, useReducedMotion } from "motion/react";
import { Database, Scissors, Search, Filter, Users, Gavel, MessageSquareText } from "lucide-react";
import { Reveal } from "@/components/ui/reveal";

const steps = [
  { icon: Database, title: "Ingest", body: "Ames Housing CSV is cleaned, typed and turned into natural-language property cases." },
  { icon: Scissors, title: "Embed & index", body: "Each case is embedded (dense) and tokenized (BM25) with structured metadata attached." },
  { icon: Search, title: "Hybrid retrieve", body: "Your query hits both indexes; results are fused with reciprocal-rank fusion." },
  { icon: Filter, title: "Filter & prioritize", body: "Metadata filters prune; a comparable-prioritization reranker scores true comps." },
  { icon: Users, title: "Agents collaborate", body: "Classifier, comp analyst, pricing model, risk analyst and valuer each contribute." },
  { icon: Gavel, title: "Judge validates", body: "An independent LLM judge checks grounding, calibration and model agreement." },
  { icon: MessageSquareText, title: "Answer", body: "A cited narrative, valuation range, risk score and feature impacts are returned." },
];

export function Pipeline() {
  const reduce = useReducedMotion();
  return (
    <section id="how" className="relative py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <div className="max-w-2xl">
            <div className="eyebrow mb-4">How it works</div>
            <h2 className="display text-[36px] sm:text-[52px] text-ink">
              From raw CSV to a <em>defensible</em> number.
            </h2>
            <p className="mt-5 text-[16px] leading-relaxed text-ink-2">
              Every answer follows the same seven-stage path. Each stage is observable in the workspace, so a reviewer
              can trace a valuation back to the exact records that produced it.
            </p>
          </div>
        </Reveal>

        <div className="relative mt-16">
          {/* connector line */}
          <motion.div
            className="absolute left-[23px] top-6 hidden w-px bg-line lg:left-0 lg:top-[27px] lg:h-px lg:w-full"
            initial={reduce ? false : { scaleX: 0, scaleY: 0 }}
            whileInView={{ scaleX: 1, scaleY: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1.6, ease: "easeOut" }}
            style={{ transformOrigin: "left top", height: "calc(100% - 48px)" }}
          />
          <ol className="grid gap-8 lg:grid-cols-7 lg:gap-4">
            {steps.map((s, i) => (
              <Reveal key={s.title} delay={i * 0.07}>
                <li className="relative flex gap-4 lg:block">
                  <div className="relative z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-line bg-surface shadow-sm">
                    <s.icon size={18} className="text-accent" />
                  </div>
                  <div className="lg:mt-5">
                    <div className="font-mono text-[11px] text-ink-3">0{i + 1}</div>
                    <h3 className="mt-1 text-[15px] font-semibold text-ink">{s.title}</h3>
                    <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">{s.body}</p>
                  </div>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
