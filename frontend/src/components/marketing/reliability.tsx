import { Reveal } from "@/components/ui/reveal";
import { ShieldCheck, Activity, LifeBuoy, FlaskConical, FileSearch, Lock } from "lucide-react";

const items = [
  { icon: ShieldCheck, title: "Guardrails in, guardrails out", body: "Inputs are validated before any model call; outputs are schema-checked and judged before they reach the UI." },
  { icon: LifeBuoy, title: "Graceful degradation", body: "LLM timeout → smaller model. Vector store down → BM25 only. Backend unreachable → demo data, clearly labelled." },
  { icon: FlaskConical, title: "Continuous evaluation", body: "A DeepEval suite runs on a golden set in CI; regressions block deploys. Scores are visible in the workspace." },
  { icon: FileSearch, title: "Full traceability", body: "Every response carries a request id, agent trace, retrieved records and the judge's criteria." },
  { icon: Activity, title: "Observability", body: "Latency percentiles, token spend and guardrail hit-rates exposed on a health endpoint and dashboard." },
  { icon: Lock, title: "Safe by default", body: "PII redaction, rate limiting, strict CORS and secrets via environment only. No data leaves the deployment." },
];

export function Reliability() {
  return (
    <section id="reliability" className="py-24 sm:py-32" style={{ background: "#141413", color: "#f7f6f2" }}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <div className="max-w-2xl">
            <div className="eyebrow mb-4" style={{ color: "rgba(247,246,242,0.5)" }}>Reliability</div>
            <h2 className="display text-[36px] sm:text-[52px]">
              Built to be <em style={{ color: "#d97757" }}>reviewed</em>, not just demoed.
            </h2>
            <p className="mt-5 text-[16px] leading-relaxed text-[color:rgba(247,246,242,0.72)]">
              Client-ready means the system tells you when it is unsure, keeps working when a dependency fails, and proves its quality with numbers.
            </p>
          </div>
        </Reveal>
        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((it, i) => (
            <Reveal key={it.title} delay={i * 0.05}>
              <div className="h-full rounded-2xl border border-[rgba(247,246,242,0.10)] bg-[rgba(247,246,242,0.04)] p-6 transition-colors hover:bg-[rgba(247,246,242,0.07)]">
                <it.icon size={20} style={{ color: "#d97757" }} />
                <h3 className="mt-5 text-[15px] font-semibold">{it.title}</h3>
                <p className="mt-2 text-[13.5px] leading-relaxed text-[color:rgba(247,246,242,0.7)]">{it.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
