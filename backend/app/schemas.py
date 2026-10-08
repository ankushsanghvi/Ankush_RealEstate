"""API contracts. Field names are camelCase on purpose: they mirror
frontend/src/lib/types.ts one-to-one so the two never drift."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Property(BaseModel):
    id: str
    neighborhood: str
    salePrice: int
    overallQual: int
    overallCond: int
    grLivArea: int
    totalBsmtSF: int
    lotArea: int
    garageCars: int
    garageArea: int
    yearBuilt: int
    yearRemodAdd: int
    garageYrBlt: int | None
    fullBath: int
    bedroomAbvGr: int
    totRmsAbvGrd: int
    saleYear: int
    bldgType: str = "OneFam"
    summary: str


class QueryFilters(BaseModel):
    neighborhoods: list[str] | None = None
    minYearBuilt: int | None = Field(default=None, ge=1800, le=2100)
    maxYearBuilt: int | None = Field(default=None, ge=1800, le=2100)
    minBedrooms: int | None = Field(default=None, ge=0, le=20)
    maxBedrooms: int | None = Field(default=None, ge=0, le=20)
    minGrLivArea: int | None = Field(default=None, ge=0, le=20000)
    maxGrLivArea: int | None = Field(default=None, ge=0, le=20000)
    minQual: int | None = Field(default=None, ge=1, le=10)
    maxPrice: int | None = Field(default=None, ge=0)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: QueryFilters = Field(default_factory=QueryFilters)
    top_k: int = Field(default=8, ge=1, le=25)


class SubjectAttributes(BaseModel):
    neighborhood: str | None = None
    bedrooms: int | None = None
    grLivArea: int | None = None
    yearBuilt: int | None = None
    overallQual: int | None = None
    garageCars: int | None = None
    totalBsmtSF: int | None = None
    lotArea: int | None = None
    fullBath: int | None = None


QueryIntent = Literal["similar_properties", "valuation", "comparison", "price_difference", "market_insight", "out_of_scope"]


class Classification(BaseModel):
    intent: QueryIntent
    confidence: float
    propertyType: Literal["single_family", "townhouse", "duplex", "unknown"]
    extractedAttributes: SubjectAttributes
    rationale: str


class Adjustment(BaseModel):
    label: str
    amount: int


class Comparable(BaseModel):
    property: Property
    semanticScore: float
    keywordScore: float
    hybridScore: float
    priorityScore: float
    priorityReasons: list[str]
    adjustments: list[Adjustment]
    adjustedPrice: int


class Valuation(BaseModel):
    estimate: int
    low: int
    high: int
    confidence: float
    method: Literal["comparable_weighted", "ml_model", "ensemble"]
    pricePerSqft: int
    narrative: str


class FeatureContribution(BaseModel):
    feature: str
    impact: int


class PricePrediction(BaseModel):
    model: str
    prediction: int
    low: int
    high: int
    mape: float
    r2: float
    featureContributions: list[FeatureContribution]


class JudgeCriterion(BaseModel):
    name: str
    pass_: bool = Field(alias="pass")
    note: str

    model_config = {"populate_by_name": True}


class JudgeVerdict(BaseModel):
    verdict: Literal["approved", "flagged", "rejected"]
    score: float
    criteria: list[JudgeCriterion]
    summary: str


class RiskDriver(BaseModel):
    label: str
    weight: int
    direction: Literal["up", "down"]


class RiskAssessment(BaseModel):
    level: Literal["low", "moderate", "elevated", "high"]
    score: int
    drivers: list[RiskDriver]
    volatility12m: float
    neighborhoodSales: int


class ImpactFactor(BaseModel):
    feature: str
    elasticity: float
    description: str


class AgentStep(BaseModel):
    agent: str
    role: str
    status: Literal["done", "running", "skipped", "error"]
    durationMs: int
    output: str
    tool: str | None = None


class GuardrailCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str


class GuardrailResult(BaseModel):
    passed: bool
    checks: list[GuardrailCheck]


class QueryResponse(BaseModel):
    requestId: str
    mode: Literal["live", "demo"] = "live"
    engine: Literal["llm", "rules", "llm-degraded"]
    query: str
    latencyMs: int
    guardrails: GuardrailResult
    classification: Classification | None = None
    comparables: list[Comparable] = []
    valuation: Valuation | None = None
    prediction: PricePrediction | None = None
    judge: JudgeVerdict | None = None
    risk: RiskAssessment | None = None
    impact: list[ImpactFactor] = []
    agentTrace: list[AgentStep] = []
    answer: str = ""


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: QueryFilters = Field(default_factory=QueryFilters)
    top_k: int = Field(default=10, ge=1, le=50)


class SearchHit(BaseModel):
    property: Property
    semanticScore: float
    keywordScore: float
    hybridScore: float


class SearchResponse(BaseModel):
    query: str
    total_candidates: int
    hits: list[SearchHit]


class ValuationRequest(SubjectAttributes):
    top_k: int = Field(default=8, ge=1, le=25)


class PredictRequest(SubjectAttributes):
    pass


class CompareRequest(BaseModel):
    a: str
    b: str


class CompareFactor(BaseModel):
    label: str
    amount: int
    why: str


class CompareResponse(BaseModel):
    a: Property
    b: Property
    difference: int
    factors: list[CompareFactor]
    explainedShare: float
    narrative: str


class PropertiesResponse(BaseModel):
    items: list[Property]
    total: int


class FeedbackPayload(BaseModel):
    requestId: str
    rating: Literal["up", "down"]
    correctedValue: int | None = Field(default=None, ge=1000, le=5_000_000)
    comment: str | None = Field(default=None, max_length=1000)


class EvalMetric(BaseModel):
    name: str
    score: float
    threshold: float
    passRate: float


class EvalHistoryPoint(BaseModel):
    date: str
    faithfulness: float
    relevancy: float
    precision: float


class EvalFeedback(BaseModel):
    positive: int
    negative: int
    corrected: int


class EvalSummary(BaseModel):
    runId: str
    ranAt: str
    cases: int
    metrics: list[EvalMetric]
    judgeAgreement: float
    history: list[EvalHistoryPoint]
    feedback: EvalFeedback
    latencyP50: int
    latencyP95: int
    source: str = "builtin"


class Health(BaseModel):
    status: str
    version: str
    engine: str
    embedding: str
    records: int
    llm: dict
    latency: dict
    uptimeS: int
