import type {
  Property, Neighborhood, QueryResponse, Comparable, EvalSummary, QueryFilters,
} from "./types";

/* Deterministic PRNG so demo data is stable between renders. */
function mulberry32(seed: number) {
  return () => {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const NEIGHBORHOODS: { code: Neighborhood; name: string; median: number }[] = [
  { code: "NridgHt", name: "Northridge Heights", median: 315000 },
  { code: "NoRidge", name: "Northridge", median: 301000 },
  { code: "StoneBr", name: "Stone Brook", median: 278000 },
  { code: "Timber", name: "Timberland", median: 228000 },
  { code: "Veenker", name: "Veenker", median: 218000 },
  { code: "Somerst", name: "Somerset", median: 225000 },
  { code: "ClearCr", name: "Clear Creek", median: 200000 },
  { code: "Crawfor", name: "Crawford", median: 200000 },
  { code: "CollgCr", name: "College Creek", median: 197000 },
  { code: "Blmngtn", name: "Bloomington Heights", median: 191000 },
  { code: "Gilbert", name: "Gilbert", median: 181000 },
  { code: "NWAmes", name: "Northwest Ames", median: 182000 },
  { code: "SawyerW", name: "Sawyer West", median: 179000 },
  { code: "Mitchel", name: "Mitchell", median: 153000 },
  { code: "NAmes", name: "North Ames", median: 140000 },
  { code: "NPkVill", name: "Northpark Villa", median: 146000 },
  { code: "SWISU", name: "South & West of ISU", median: 139000 },
  { code: "Blueste", name: "Bluestem", median: 137000 },
  { code: "Greens", name: "Greens", median: 193000 },
  { code: "GrnHill", name: "Green Hills", median: 280000 },
  { code: "Landmrk", name: "Landmark", median: 137000 },
  { code: "Sawyer", name: "Sawyer", median: 135000 },
  { code: "OldTown", name: "Old Town", median: 119000 },
  { code: "Edwards", name: "Edwards", median: 121000 },
  { code: "BrkSide", name: "Brookside", median: 124000 },
  { code: "BrDale", name: "Briardale", median: 106000 },
  { code: "IDOTRR", name: "Iowa DOT & Rail Road", median: 103000 },
  { code: "MeadowV", name: "Meadow Village", median: 88000 },
];

const nbName = (c: Neighborhood) => NEIGHBORHOODS.find((n) => n.code === c)?.name ?? c;

function describe(p: Property) {
  const age = p.saleYear - p.yearBuilt;
  const remod = p.yearRemodAdd > p.yearBuilt ? `, remodeled ${p.yearRemodAdd}` : "";
  return `${p.bedroomAbvGr}-bedroom, ${p.fullBath}-bath home in ${nbName(p.neighborhood)} with ${p.grLivArea.toLocaleString()} sq ft above grade, ${p.totalBsmtSF.toLocaleString()} sq ft basement and a ${p.garageCars}-car garage. Built ${p.yearBuilt}${remod} (${age} yrs old at sale). Overall quality ${p.overallQual}/10, condition ${p.overallCond}/10, on a ${p.lotArea.toLocaleString()} sq ft lot. Sold ${p.saleYear} for $${p.salePrice.toLocaleString()}.`;
}

export function generateProperties(count = 240, seed = 7): Property[] {
  const rnd = mulberry32(seed);
  const out: Property[] = [];
  for (let i = 0; i < count; i++) {
    const nb = NEIGHBORHOODS[Math.floor(rnd() * NEIGHBORHOODS.length)];
    const qual = Math.max(2, Math.min(10, Math.round(nb.median / 42000 + (rnd() - 0.5) * 3)));
    const yearBuilt = Math.round(1900 + Math.pow(rnd(), 0.6) * 109);
    const yearRemodAdd = rnd() < 0.4 ? Math.min(2009, yearBuilt + Math.round(rnd() * 40)) : Math.max(yearBuilt, 1950);
    const grLivArea = Math.round(700 + Math.pow(rnd(), 1.4) * 2400 + qual * 60);
    const totalBsmtSF = Math.round(rnd() < 0.08 ? 0 : grLivArea * (0.45 + rnd() * 0.55));
    const garageCars = rnd() < 0.08 ? 0 : Math.min(3, Math.round(1 + rnd() * 2));
    const base = nb.median * (0.55 + (grLivArea / 1500) * 0.5) * (0.7 + qual * 0.05) * (0.85 + ((yearBuilt - 1900) / 110) * 0.3);
    const salePrice = Math.round((base * (0.88 + rnd() * 0.24)) / 500) * 500;
    const saleYear = 2006 + Math.floor(rnd() * 5);
    const p: Property = {
      id: `AMES-${String(1000 + i).padStart(4, "0")}`,
      neighborhood: nb.code,
      salePrice,
      overallQual: qual,
      overallCond: Math.max(2, Math.min(9, Math.round(5 + (rnd() - 0.5) * 4))),
      grLivArea,
      totalBsmtSF,
      lotArea: Math.round(5000 + Math.pow(rnd(), 2.2) * 25000),
      garageCars,
      garageArea: garageCars === 0 ? 0 : Math.round(garageCars * (240 + rnd() * 90)),
      yearBuilt,
      yearRemodAdd,
      garageYrBlt: garageCars === 0 ? null : Math.max(yearBuilt, yearRemodAdd - Math.round(rnd() * 5)),
      fullBath: Math.min(3, Math.max(1, Math.round(grLivArea / 900))),
      bedroomAbvGr: Math.min(5, Math.max(1, Math.round(grLivArea / 520))),
      totRmsAbvGrd: Math.min(12, Math.max(4, Math.round(grLivArea / 260))),
      saleYear,
      summary: "",
    };
    p.summary = describe(p);
    out.push(p);
  }
  return out;
}

export const PROPERTIES = generateProperties();

export function applyFilters(list: Property[], f: QueryFilters) {
  return list.filter((p) => {
    if (f.neighborhoods?.length && !f.neighborhoods.includes(p.neighborhood)) return false;
    if (f.minYearBuilt && p.yearBuilt < f.minYearBuilt) return false;
    if (f.maxYearBuilt && p.yearBuilt > f.maxYearBuilt) return false;
    if (f.minBedrooms && p.bedroomAbvGr < f.minBedrooms) return false;
    if (f.maxBedrooms && p.bedroomAbvGr > f.maxBedrooms) return false;
    if (f.minGrLivArea && p.grLivArea < f.minGrLivArea) return false;
    if (f.maxGrLivArea && p.grLivArea > f.maxGrLivArea) return false;
    if (f.minQual && p.overallQual < f.minQual) return false;
    if (f.maxPrice && p.salePrice > f.maxPrice) return false;
    return true;
  });
}

/* Parse a few attributes out of a natural-language query. */
function extract(query: string) {
  const q = query.toLowerCase();
  const nb = NEIGHBORHOODS.find((n) => q.includes(n.name.toLowerCase()) || q.includes(n.code.toLowerCase()));
  const bed = q.match(/(\d)\s*-?\s*(bed|br\b|bedroom)/);
  const sqft = q.match(/(\d[\d,]{2,})\s*(sq|sqft|square)/);
  const year = q.match(/(built|from|in)\s*(19|20)(\d{2})/);
  const qual = q.match(/quality\s*(\d{1,2})/);
  const garage = q.match(/(\d)\s*-?\s*car/);
  return {
    neighborhood: nb?.code,
    bedrooms: bed ? Number(bed[1]) : undefined,
    grLivArea: sqft ? Number(sqft[1].replace(/,/g, "")) : undefined,
    yearBuilt: year ? Number(`${year[2]}${year[3]}`) : undefined,
    overallQual: qual ? Number(qual[1]) : undefined,
    garageCars: garage ? Number(garage[1]) : undefined,
  };
}

export function mockQuery(query: string, filters: QueryFilters = {}): QueryResponse {
  const rnd = mulberry32(query.length * 31 + 11);
  const attrs = extract(query);
  const subject = {
    neighborhood: attrs.neighborhood ?? filters.neighborhoods?.[0] ?? ("CollgCr" as Neighborhood),
    bedrooms: attrs.bedrooms ?? filters.minBedrooms ?? 3,
    grLivArea: attrs.grLivArea ?? filters.minGrLivArea ?? 1650,
    yearBuilt: attrs.yearBuilt ?? filters.minYearBuilt ?? 1998,
    overallQual: attrs.overallQual ?? filters.minQual ?? 7,
    garageCars: attrs.garageCars ?? 2,
  };

  const pool = applyFilters(PROPERTIES, filters);
  const scored: Comparable[] = pool
    .map((p) => {
      const dArea = Math.abs(p.grLivArea - subject.grLivArea) / subject.grLivArea;
      const dYear = Math.abs(p.yearBuilt - subject.yearBuilt) / 40;
      const dQual = Math.abs(p.overallQual - subject.overallQual) / 5;
      const sameNb = p.neighborhood === subject.neighborhood;
      const semantic = Math.max(0.3, 1 - (dArea * 0.5 + dYear * 0.25 + dQual * 0.3) - (sameNb ? 0 : 0.12) + (rnd() - 0.5) * 0.05);
      const keyword = Math.max(0.1, (sameNb ? 0.6 : 0.2) + (p.bedroomAbvGr === subject.bedrooms ? 0.25 : 0) + rnd() * 0.15);
      const hybrid = 0.65 * semantic + 0.35 * keyword;
      const reasons: string[] = [];
      if (sameNb) reasons.push("Same neighborhood");
      if (dArea < 0.1) reasons.push(`Living area within ${Math.round(dArea * 100)}%`);
      if (Math.abs(p.yearBuilt - subject.yearBuilt) <= 8) reasons.push("Built within 8 years");
      if (p.overallQual === subject.overallQual) reasons.push("Identical quality grade");
      if (p.bedroomAbvGr === subject.bedrooms) reasons.push("Same bedroom count");
      if (p.saleYear >= 2009) reasons.push("Recent sale");
      const priority = Math.min(1, hybrid * 0.7 + reasons.length * 0.06);
      const ppsf = p.salePrice / p.grLivArea;
      const adjustments = [
        { label: "Living area", amount: Math.round((subject.grLivArea - p.grLivArea) * ppsf * 0.6) },
        { label: "Quality grade", amount: Math.round((subject.overallQual - p.overallQual) * 9500) },
        { label: "Age", amount: Math.round((subject.yearBuilt - p.yearBuilt) * 420) },
        { label: "Garage", amount: Math.round((subject.garageCars - p.garageCars) * 7800) },
      ].filter((a) => a.amount !== 0);
      const adjustedPrice = p.salePrice + adjustments.reduce((s, a) => s + a.amount, 0);
      return {
        property: p,
        semanticScore: semantic,
        keywordScore: Math.min(1, keyword),
        hybridScore: hybrid,
        priorityScore: priority,
        priorityReasons: reasons,
        adjustments,
        adjustedPrice,
      };
    })
    .sort((a, b) => b.priorityScore - a.priorityScore)
    .slice(0, 8);

  const weights = scored.map((c) => c.priorityScore ** 2);
  const wsum = weights.reduce((a, b) => a + b, 0) || 1;
  const estimate = Math.round(scored.reduce((s, c, i) => s + c.adjustedPrice * weights[i], 0) / wsum / 500) * 500;
  const spread = scored.length ? Math.sqrt(scored.reduce((s, c) => s + (c.adjustedPrice - estimate) ** 2, 0) / scored.length) : estimate * 0.08;
  const confidence = Math.max(0.42, Math.min(0.94, 1 - spread / estimate - (8 - scored.length) * 0.03));
  const mlPred = Math.round((estimate * (0.97 + rnd() * 0.06)) / 500) * 500;

  const sameNbCount = scored.filter((c) => c.property.neighborhood === subject.neighborhood).length;
  const nb = NEIGHBORHOODS.find((n) => n.code === subject.neighborhood)!;

  const diff = Math.abs(mlPred - estimate) / estimate;
  const judgeScore = Math.max(0.5, Math.min(0.98, 0.95 - diff * 2 - (confidence < 0.6 ? 0.1 : 0)));
  const verdict = judgeScore > 0.8 ? "approved" : judgeScore > 0.65 ? "flagged" : "rejected";

  const riskScore = Math.round(22 + (1 - confidence) * 60 + (sameNbCount < 3 ? 12 : 0));
  const riskLevel = riskScore < 30 ? "low" : riskScore < 50 ? "moderate" : riskScore < 70 ? "elevated" : "high";

  const rangeLow = Math.round((estimate - spread * 1.1) / 500) * 500;
  const rangeHigh = Math.round((estimate + spread * 1.1) / 500) * 500;
  const outOfScope = /\b(stock|crypto|weather|recipe|joke)\b/i.test(query);
  const tooShort = query.trim().length < 8;

  return {
    requestId: `req_${Math.floor(rnd() * 1e8).toString(16)}`,
    mode: "demo",
    engine: "rules",
    query,
    latencyMs: 1240 + Math.round(rnd() * 900),
    guardrails: {
      passed: !outOfScope && !tooShort,
      checks: [
        { name: "Length & encoding", status: tooShort ? "fail" : "pass", detail: tooShort ? "Query too short to be actionable" : `${query.trim().split(/\s+/).length} tokens, UTF-8 clean` },
        { name: "Prompt-injection scan", status: "pass", detail: "No instruction-override patterns detected" },
        { name: "Domain relevance", status: outOfScope ? "fail" : "pass", detail: outOfScope ? "Query is outside real-estate valuation scope" : "Real-estate intent detected" },
        { name: "PII redaction", status: "pass", detail: "No personal identifiers present" },
        { name: "Attribute sanity", status: subject.grLivArea > 6000 ? "warn" : "pass", detail: subject.grLivArea > 6000 ? "Living area outside dataset range; clamped" : "All extracted values within dataset bounds" },
      ],
    },
    classification: {
      intent: /differ|why|explain|compare/i.test(query) ? "price_difference" : /worth|value|estimate|price/i.test(query) ? "valuation" : "similar_properties",
      confidence: 0.86 + rnd() * 0.1,
      propertyType: "single_family",
      extractedAttributes: { ...subject, bedrooms: subject.bedrooms },
      rationale: `Detected ${subject.bedrooms}-bedroom single-family intent anchored on ${nb.name}. Query asks for ${/worth|value|estimate/i.test(query) ? "a valuation" : "comparable sales"}; routing to the valuation pipeline with comparable retrieval.`,
    },
    comparables: scored,
    valuation: {
      estimate,
      low: rangeLow,
      high: rangeHigh,
      confidence,
      method: "ensemble",
      pricePerSqft: Math.round(estimate / subject.grLivArea),
      narrative: `Weighted ${scored.length} prioritized comparables (${sameNbCount} in ${nb.name}) after appraisal-style adjustments for living area, quality, age and garage capacity. The gradient-boosted model independently predicts ${mlPred >= estimate ? "slightly above" : "slightly below"} the comparable-weighted figure; the ensemble leans on comparables where neighborhood coverage is strong.`,
    },
    prediction: {
      model: "GradientBoostingRegressor · v3 (log-target)",
      prediction: mlPred,
      low: Math.round(mlPred * 0.91),
      high: Math.round(mlPred * 1.09),
      mape: 0.089,
      r2: 0.912,
      featureContributions: [
        { feature: "OverallQual", impact: Math.round((subject.overallQual - 6) * 14500) },
        { feature: "GrLivArea", impact: Math.round((subject.grLivArea - 1500) * 48) },
        { feature: "Neighborhood", impact: Math.round((nb.median - 180000) * 0.45) },
        { feature: "YearBuilt", impact: Math.round((subject.yearBuilt - 1975) * 380) },
        { feature: "GarageCars", impact: Math.round((subject.garageCars - 1.7) * 9800) },
        { feature: "TotalBsmtSF", impact: Math.round(rnd() * 9000 - 2000) },
        { feature: "LotArea", impact: Math.round(rnd() * 6000 - 1500) },
      ].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)),
    },
    judge: {
      verdict,
      score: judgeScore,
      criteria: [
        { name: "Comparable relevance", pass: sameNbCount >= 2, note: `${sameNbCount}/${scored.length} comparables share the subject neighborhood` },
        { name: "Model agreement", pass: diff < 0.08, note: `Comparable vs. ML estimate differ by ${(diff * 100).toFixed(1)}%` },
        { name: "Adjustment reasonableness", pass: true, note: "Net adjustments within ±15% of sale price on all comps" },
        { name: "Grounded narrative", pass: true, note: "Every claim in the narrative cites a retrieved record" },
        { name: "Range calibration", pass: confidence > 0.55, note: `Interval width ${((spread * 2.2) / estimate * 100).toFixed(0)}% of estimate` },
      ],
      summary: verdict === "approved" ? "Valuation is well-supported by in-neighborhood comparables and corroborated by the ML model." : verdict === "flagged" ? "Valuation is plausible but the two methods diverge; recommend reviewing the adjustment set before publishing." : "Insufficient comparable coverage; valuation should not be relied upon without manual review.",
    },
    risk: {
      level: riskLevel,
      score: riskScore,
      drivers: [
        { label: "Comparable dispersion", weight: Math.round((spread / estimate) * 100), direction: "up" },
        { label: "Neighborhood coverage", weight: sameNbCount >= 3 ? 8 : 22, direction: sameNbCount >= 3 ? "down" : "up" },
        { label: "Property age", weight: Math.max(2, Math.round((2010 - subject.yearBuilt) / 4)), direction: "up" },
        { label: "Quality grade", weight: subject.overallQual >= 7 ? 10 : 4, direction: "down" },
      ],
      volatility12m: 0.04 + rnd() * 0.06,
      neighborhoodSales: 40 + Math.round(rnd() * 200),
    },
    impact: [
      { feature: "OverallQual", elasticity: 0.11, description: "Each quality point adds ~11% to expected price, the strongest single driver in the dataset." },
      { feature: "GrLivArea", elasticity: 0.064, description: "Every additional 100 sq ft above grade adds ~6.4%; the effect flattens past 2,800 sq ft." },
      { feature: "Neighborhood", elasticity: 0.38, description: `${nb.name} carries a ${nb.median > 180000 ? "premium" : "discount"} of ${Math.abs(Math.round(((nb.median - 180000) / 180000) * 100))}% relative to the city median.` },
      { feature: "YearBuilt", elasticity: 0.021, description: "Newer construction commands ~2.1% per decade after controlling for quality." },
      { feature: "GarageCars", elasticity: 0.045, description: "A second garage bay adds ~4.5%; a third adds a further 2%." },
      { feature: "TotalBsmtSF", elasticity: 0.028, description: "Finished basement area contributes ~2.8% per 500 sq ft." },
    ],
    agentTrace: [
      { agent: "Guardrail", role: "Input validation", status: "done", durationMs: 42, output: "5 checks passed · intent in scope", tool: "rules + classifier" },
      { agent: "Classifier", role: "Intent & attribute extraction", status: "done", durationMs: 610, output: `intent=valuation · ${nb.code}, ${subject.bedrooms}bd, ${subject.grLivArea} sqft, built ${subject.yearBuilt}`, tool: "llm:structured-output" },
      { agent: "Retriever", role: "Hybrid search", status: "done", durationMs: 184, output: `BM25 ∪ dense → 40 candidates · RRF fused · metadata filter kept ${pool.length}`, tool: "bm25 + vector store" },
      { agent: "Comp Analyst", role: "Prioritization & adjustments", status: "done", durationMs: 920, output: `Top ${scored.length} comparables · net adjustments computed`, tool: "llm + rules" },
      { agent: "Pricing Model", role: "ML prediction", status: "done", durationMs: 38, output: `$${mlPred.toLocaleString()} (±9%)`, tool: "sklearn" },
      { agent: "Risk Analyst", role: "Volatility & liquidity", status: "done", durationMs: 450, output: `${riskLevel} risk · score ${riskScore}`, tool: "llm + stats" },
      { agent: "Valuer", role: "Ensemble synthesis", status: "done", durationMs: 1100, output: `$${estimate.toLocaleString()} · conf ${(confidence * 100).toFixed(0)}%`, tool: "llm" },
      { agent: "Judge", role: "Validation", status: "done", durationMs: 780, output: `${verdict} · ${(judgeScore * 100).toFixed(0)}/100`, tool: "llm-as-judge" },
    ],
    answer: `Based on ${scored.length} prioritized comparable sales, a ${subject.bedrooms}-bedroom home of ${subject.grLivArea.toLocaleString()} sq ft in ${nb.name} built around ${subject.yearBuilt} with quality grade ${subject.overallQual} is estimated at $${estimate.toLocaleString()} (range $${rangeLow.toLocaleString()} – $${rangeHigh.toLocaleString()}). The strongest comparable is ${scored[0]?.property.id} which sold for $${scored[0]?.property.salePrice.toLocaleString()} and adjusts to $${scored[0]?.adjustedPrice.toLocaleString()}. Quality grade and living area explain most of the spread across comparables.`,
  };
}

export const MOCK_EVAL: EvalSummary = {
  runId: "eval_2026-10-06_1842",
  ranAt: "2026-10-06T18:42:00Z",
  cases: 120,
  metrics: [
    { name: "Faithfulness", score: 0.93, threshold: 0.85, passRate: 0.95 },
    { name: "Answer relevancy", score: 0.91, threshold: 0.8, passRate: 0.96 },
    { name: "Contextual precision", score: 0.87, threshold: 0.75, passRate: 0.92 },
    { name: "Contextual recall", score: 0.84, threshold: 0.75, passRate: 0.9 },
    { name: "Hallucination", score: 0.06, threshold: 0.1, passRate: 0.97 },
    { name: "Valuation MAPE", score: 0.089, threshold: 0.12, passRate: 0.88 },
  ],
  judgeAgreement: 0.91,
  history: [
    { date: "Sep 08", faithfulness: 0.82, relevancy: 0.84, precision: 0.74 },
    { date: "Sep 15", faithfulness: 0.85, relevancy: 0.86, precision: 0.78 },
    { date: "Sep 22", faithfulness: 0.88, relevancy: 0.88, precision: 0.8 },
    { date: "Sep 29", faithfulness: 0.9, relevancy: 0.9, precision: 0.84 },
    { date: "Oct 06", faithfulness: 0.93, relevancy: 0.91, precision: 0.87 },
  ],
  feedback: { positive: 312, negative: 41, corrected: 27 },
  latencyP50: 1680,
  latencyP95: 3240,
};
