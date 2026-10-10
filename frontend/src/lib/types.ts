/* ------------------------------------------------------------------
   Shared API contracts. The FastAPI backend mirrors these shapes.
   ------------------------------------------------------------------ */

export type Neighborhood = string; // Ames neighborhood code, e.g. "CollgCr"

export interface Property {
  id: string;
  neighborhood: Neighborhood;
  salePrice: number;
  overallQual: number;       // 1–10
  overallCond: number;       // 1–10
  grLivArea: number;         // sq ft above grade
  totalBsmtSF: number;
  lotArea: number;
  garageCars: number;
  garageArea: number;
  yearBuilt: number;
  yearRemodAdd: number;
  garageYrBlt: number | null;
  fullBath: number;
  bedroomAbvGr: number;
  totRmsAbvGrd: number;
  saleYear: number;
  bldgType?: string;
  summary: string;           // generated natural-language case description
}

export interface QueryFilters {
  neighborhoods?: Neighborhood[];
  minYearBuilt?: number;
  maxYearBuilt?: number;
  minBedrooms?: number;
  maxBedrooms?: number;
  minGrLivArea?: number;
  maxGrLivArea?: number;
  minQual?: number;
  maxPrice?: number;
}

export type QueryIntent =
  | "similar_properties"
  | "valuation"
  | "comparison"
  | "price_difference"
  | "market_insight"
  | "out_of_scope";

export interface Classification {
  intent: QueryIntent;
  confidence: number;
  propertyType: "single_family" | "townhouse" | "duplex" | "unknown";
  extractedAttributes: Partial<{
    neighborhood: Neighborhood;
    bedrooms: number;
    grLivArea: number;
    yearBuilt: number;
    overallQual: number;
    garageCars: number;
  }>;
  rationale: string;
}

export interface Comparable {
  property: Property;
  semanticScore: number;     // 0–1 cosine
  keywordScore: number;      // 0–1 normalized BM25
  hybridScore: number;       // 0–1 fused (RRF)
  priorityScore: number;     // 0–1 after comparable-prioritization rerank
  priorityReasons: string[]; // "same neighborhood", "±8% living area", …
  adjustments: { label: string; amount: number }[]; // appraisal-style adjustments
  adjustedPrice: number;
}

export interface Valuation {
  estimate: number;
  low: number;
  high: number;
  confidence: number;        // 0–1
  method: "comparable_weighted" | "ml_model" | "ensemble";
  pricePerSqft: number;
  narrative: string;
  priceBasis?: string;       // sale years / market the figures come from, e.g. "Historical Ames, Iowa sales 2006–2010 …"
}

export interface PricePrediction {
  model: string;             // "GradientBoosting v3"
  prediction: number;
  low: number;
  high: number;
  mape: number;              // validation error
  r2: number;
  featureContributions: { feature: string; impact: number }[]; // SHAP-like, in $
}

export interface JudgeVerdict {
  verdict: "approved" | "flagged" | "rejected";
  score: number;             // 0–1
  criteria: { name: string; pass: boolean; note: string }[];
  summary: string;
}

export interface RiskAssessment {
  level: "low" | "moderate" | "elevated" | "high";
  score: number;             // 0–100
  drivers: { label: string; weight: number; direction: "up" | "down" }[];
  volatility12m: number;     // neighborhood price-per-sqft dispersion (CV)
  neighborhoodSales: number; // sales in the neighborhood within the dataset
}

export interface AgentStep {
  agent: string;
  role: string;
  status: "done" | "running" | "skipped" | "error";
  durationMs: number;
  output: string;
  tool?: string;
}

export interface GuardrailResult {
  passed: boolean;
  checks: { name: string; status: "pass" | "warn" | "fail"; detail: string }[];
}

export interface QueryResponse {
  requestId: string;
  mode: "live" | "demo";
  engine?: "llm" | "rules" | "llm-degraded"; // which engine answered
  query: string;
  latencyMs: number;
  guardrails: GuardrailResult;
  classification: Classification | null;
  comparables: Comparable[];
  valuation: Valuation | null;
  prediction: PricePrediction | null;
  judge: JudgeVerdict | null;
  risk: RiskAssessment | null;
  impact: { feature: string; elasticity: number; description: string }[];
  agentTrace: AgentStep[];
  answer: string;            // final synthesized narrative
}

export interface EvalSummary {
  runId: string;
  ranAt: string;
  cases: number;
  metrics: { name: string; score: number; threshold: number; passRate: number }[];
  judgeAgreement: number;
  history: { date: string; faithfulness: number; relevancy: number; precision: number }[];
  feedback: { positive: number; negative: number; corrected: number };
  latencyP50: number;
  latencyP95: number;
  source?: string;           // "builtin" | "deepeval" | "none"
}

export interface FeedbackPayload {
  requestId: string;
  rating: "up" | "down";
  correctedValue?: number;
  comment?: string;
}

export interface CompareFactor { label: string; amount: number; why: string }
export interface CompareResponse {
  a: Property; b: Property; difference: number; factors: CompareFactor[]; explainedShare: number; narrative: string;
}
