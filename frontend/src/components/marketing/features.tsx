import { Reveal } from "@/components/ui/reveal";
import { Badge } from "@/components/ui/badge";
import {
  Search, Layers, Tags, SlidersHorizontal, Calculator, ShieldCheck, ListOrdered,
  FlaskConical, TrendingUp, Gavel, Users, AlertTriangle, BarChart3, RefreshCcw,
} from "lucide-react";

const basic = [
  { icon: Search, title: "Semantic property RAG", body: "Dense retrieval over natural-language property cases generated from every record." },
  { icon: Layers, title: "Hybrid search", body: "BM25 keyword matching fused with embeddings via reciprocal-rank fusion." },
  { icon: Tags, title: "Classification agent", body: "Detects intent, property type and extracts structured attributes from the query." },
  { icon: SlidersHorizontal, title: "Metadata filtering", body: "Neighborhood, age, rooms and size filters applied before ranking." },
  { icon: Calculator, title: "Valuation recommendation", body: "Weighted, adjusted comparable approach with an explicit price range." },
  { icon: ShieldCheck, title: "Input guardrails", body: "Length, injection, domain, PII and attribute-range checks on every request." },
  { icon: ListOrdered, title: "Comparable prioritization", body: "Re-ranks by neighborhood, size, age and quality proximity with reasons." },
];
const advanced = [
  { icon: FlaskConical, title: "DeepEval quality suite", body: "Faithfulness, relevancy, precision and hallucination scored on a golden set." },
  { icon: TrendingUp, title: "Price prediction", body: "Gradient-boosted regressor with per-feature contributions for each estimate." },
  { icon: Gavel, title: "LLM-as-judge", body: "Independent validator approves, flags or rejects valuations with criteria." },
  { icon: Users, title: "Multi-agent collaboration", body: "Specialist agents hand off through a typed state graph with full tracing." },
  { icon: AlertTriangle, title: "Value-risk prediction", body: "Dispersion, coverage, age and volatility roll into a 0–100 risk score." },
  { icon: BarChart3, title: "Feature & location impact", body: "Elasticities quantify what each attribute and neighborhood contributes." },
  { icon: RefreshCcw, title: "Feedback loop", body: "Thumbs, corrections and comments feed the eval set and reranker weights." },
];

function Grid({ items }: { items: typeof basic }) {
  return (
    <div className="grid gap-px overflow-hidden rounded-[22px] border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
      {items.map((f, i) => (
        <Reveal key={f.title} delay={i * 0.04} className={i === items.length - 1 && items.length % 3 === 1 ? "sm:col-span-2 lg:col-span-3" : i === items.length - 1 && items.length % 2 === 1 ? "sm:col-span-2 lg:col-span-1" : undefined}>
          <div className="group h-full bg-surface p-6 transition-colors hover:bg-paper">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-2 text-accent transition-transform duration-300 group-hover:-translate-y-0.5">
              <f.icon size={18} />
            </div>
            <h3 className="mt-5 text-[15px] font-semibold text-ink">{f.title}</h3>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">{f.body}</p>
          </div>
        </Reveal>
      ))}
    </div>
  );
}

export function Features() {
  return (
    <section id="capabilities" className="bg-paper-2 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <div className="max-w-2xl">
            <div className="eyebrow mb-4">Capabilities</div>
            <h2 className="display text-[36px] sm:text-[52px] text-ink">
              Everything a valuation desk needs, <em>and the checks</em> to trust it.
            </h2>
          </div>
        </Reveal>

        <div className="mt-14">
          <div className="mb-4 flex items-center gap-3">
            <Badge tone="neutral">Requirement 1</Badge>
            <span className="text-sm text-ink-2">Core retrieval & valuation</span>
          </div>
          <Grid items={basic} />
        </div>

        <div className="mt-14">
          <div className="mb-4 flex items-center gap-3">
            <Badge tone="accent">Requirement 2</Badge>
            <span className="text-sm text-ink-2">Advanced evaluation, prediction & collaboration</span>
          </div>
          <Grid items={advanced} />
        </div>
      </div>
    </section>
  );
}
