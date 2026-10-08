import { Shell } from "@/components/app/shell";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const endpoints = [
  { method: "POST", path: "/api/v1/query", desc: "End-to-end pipeline: guardrails → classify → hybrid retrieve → prioritize → predict → risk → valuation → judge.", body: `{ "query": "3-bed in College Creek, 1650 sqft, built 1998", "filters": { "neighborhoods": ["CollgCr"], "minYearBuilt": 1990 }, "top_k": 8 }` },
  { method: "POST", path: "/api/v1/search", desc: "Hybrid search only (BM25 + dense, RRF fused) with metadata filters. Returns ranked property cases and both score components.", body: `{ "query": "ranch with finished basement", "filters": { "minGrLivArea": 1200 }, "top_k": 10 }` },
  { method: "POST", path: "/api/v1/classify", desc: "Classification agent: intent, property type and extracted attributes as a strict JSON schema.", body: `{ "query": "what is a 4-bedroom Somerset house worth?" }` },
  { method: "POST", path: "/api/v1/valuation", desc: "Valuation from explicit attributes (no NL parsing). Comparable-weighted + ML ensemble with judge verdict.", body: `{ "neighborhood": "Somerst", "grLivArea": 2000, "yearBuilt": 2005, "overallQual": 8, "bedroomAbvGr": 4, "garageCars": 2 }` },
  { method: "POST", path: "/api/v1/predict", desc: "ML price prediction only, with per-feature contributions.", body: `{ "neighborhood": "NAmes", "grLivArea": 1400, "yearBuilt": 1965, "overallQual": 5, "totalBsmtSF": 900, "garageCars": 1, "lotArea": 8500 }` },
  { method: "POST", path: "/api/v1/compare", desc: "Explain the price gap between two record ids as attributed factors.", body: `{ "a": "AMES-1012", "b": "AMES-1057" }` },
  { method: "POST", path: "/api/v1/properties", desc: "Filter and page the indexed records.", body: `{ "neighborhoods": ["OldTown"], "maxPrice": 150000 }` },
  { method: "POST", path: "/api/v1/feedback", desc: "Record a rating, optional corrected value and comment against a request id.", body: `{ "requestId": "req_3f9a1c", "rating": "down", "correctedValue": 198000, "comment": "Comps ignored the 2008 remodel" }` },
  { method: "GET", path: "/api/v1/evaluation/latest", desc: "Latest DeepEval run summary, trend history and feedback counts.", body: "" },
  { method: "GET", path: "/health", desc: "Liveness + dependency status (vector store, model, LLM provider) and latency percentiles.", body: "" },
];

export default function DocsPage() {
  return (
    <Shell title="API reference" subtitle="FastAPI microservice · JSON over HTTPS · OpenAPI at /docs">
      <div className="space-y-5">
        <Card>
          <CardBody className="pt-5 text-[13.5px] leading-relaxed text-ink-2">
            <p>
              The frontend is a thin client over a FastAPI service. Set <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[12px] text-ink">NEXT_PUBLIC_API_URL</code> to point the workspace at a deployment. Every response includes a <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[12px] text-ink">requestId</code> and, for the pipeline endpoint, the full agent trace and judge verdict.
              Errors follow RFC 9457 problem details. Requests are rate-limited per key and validated with Pydantic before any model call.
            </p>
          </CardBody>
        </Card>
        {endpoints.map((e) => (
          <Card key={e.path}>
            <CardHeader
              title={<span className="flex items-center gap-2 font-mono text-[14px]"><Badge tone={e.method === "GET" ? "sky" : "accent"} className="font-mono">{e.method}</Badge>{e.path}</span>}
              subtitle={e.desc}
            />
            {e.body && (
              <CardBody>
                <pre className="overflow-x-auto rounded-xl bg-ink p-4 font-mono text-[12px] leading-relaxed text-paper"><code>{e.body}</code></pre>
              </CardBody>
            )}
          </Card>
        ))}
      </div>
    </Shell>
  );
}
