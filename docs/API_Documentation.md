# Valora — API Documentation

FastAPI microservice exposing the property-valuation pipeline. Interactive OpenAPI (Swagger) docs are served at `http://localhost:8000/docs` and the raw schema at `/openapi.json` while the backend runs.

Every sample response below was produced by calling the real service in-process (`docs/build_docs.py`, rules engine, no API key). Long arrays are abridged with `… N more`.

## Conventions

| Item | Value |
|---|---|
| Base URL (local) | `http://localhost:8000` |
| Content type | `application/json` (UTF-8) |
| Authentication | None (local evaluation build). Secrets such as `ANTHROPIC_API_KEY` stay server-side in `.env`. |
| Field naming | camelCase, mirrored one-to-one in `frontend/src/lib/types.ts` |
| Validation | Pydantic on every request; invalid input → `422` with FastAPI's standard `detail` array |
| Errors | RFC 9457 problem details (`type`, `title`, `status`, `detail`) for 4xx/5xx raised by the service |
| Rate limit | 60 requests / minute / client IP (sliding window) → `429` |
| CORS | explicit origins (`CORS_ORIGINS`, default `http://localhost:3000`) |

## Endpoint summary

| # | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | `GET` | `/health` | Service health |
| 2 | `GET` | `/api/v1/meta` | Dataset metadata |
| 3 | `POST` | `/api/v1/query` | Natural-language valuation (full multi-agent pipeline) |
| 4 | `POST` | `/api/v1/search` | Hybrid property search |
| 5 | `POST` | `/api/v1/classify` | Property / intent classification |
| 6 | `POST` | `/api/v1/valuation` | Valuation from explicit attributes |
| 7 | `POST` | `/api/v1/predict` | ML price prediction |
| 8 | `POST` | `/api/v1/compare` | Explain a price difference between two records |
| 9 | `POST` | `/api/v1/properties` | Browse / filter records |
| 10 | `POST` | `/api/v1/feedback` | Submit feedback (continuous-improvement loop) |
| 11 | `GET` | `/api/v1/evaluation/latest` | Latest evaluation results |

## 1. Service health

**`GET /health`**

Liveness and dependency status: active engine (`llm` or `rules`), embedding model, vector store, record count, LLM circuit-breaker state, latency percentiles and uptime. Used by the UI status badge and the hosting health check.

**Request format** — no body

**Response format** — `Health` (`200 OK`)

| Field | Type | Notes |
|---|---|---|
| `status` | string |  |
| `version` | string |  |
| `engine` | string |  |
| `embedding` | string |  |
| `vectorStore` | string | optional |
| `records` | integer |  |
| `llm` | object |  |
| `latency` | object |  |
| `uptimeS` | integer |  |

**Sample request**

```bash
curl -s -X GET 'http://localhost:8000/health'
```

**Sample response** (`200`)

```json
{
  "status": "ok",
  "version": "1.0.0",
  "engine": "rules",
  "embedding": "fastembed:BAAI/bge-small-en-v1.5",
  "vectorStore": "faiss:IndexFlatIP(384d)",
  "records": 2927,
  "llm": {
    "enabled": false,
    "provider": "https://aicredits.in",
    "model": null,
    "fallbackModel": null,
    "fastModel": null,
    "apiFormat": "messages",
    "structuredOutput": "json",
    "calls": 0,
    "failures": 0,
    "degradedCalls": 0,
    "avgLatencyMs": null,
    "lastError": null,
    "circuitOpenForS": null
  },
  "latency": {
    "p50": null,
    "p95": null,
    "n": 0
  },
  "uptimeS": 0
}
```

## 2. Dataset metadata

**`GET /api/v1/meta`**

Neighborhood list with sale counts, medians and $/sq ft (sorted by median price), the dataset bounds used for attribute clamping, and the pricing model's cross-validated metrics. Drives the filter panel.

**Request format** — no body

**Response format** — JSON object (`200 OK`) with keys: `neighborhoods`, `bounds`, `records`, `model`

**Sample request**

```bash
curl -s -X GET 'http://localhost:8000/api/v1/meta'
```

**Sample response** (`200`)

```json
{
  "neighborhoods": [
    {
      "code": "StoneBr",
      "name": "Stone Brook",
      "count": 51,
      "median": 319000,
      "ppsf_median": 157.86452353616534,
      "ppsf_cv": 0.21820843215617106,
      "median_year": 2004,
      "median_qual": 8.0
    },
    {
      "code": "NridgHt",
      "name": "Northridge Heights",
      "count": 166,
      "median": 317750,
      "ppsf_median": 160.3628799006391,
      "ppsf_cv": 0.18178779972770087,
      "median_year": 2006,
      "median_qual": 8.0
    },
    "… 26 more"
  ],
  "bounds": {
    "grLivArea": [
      334,
      4476
    ],
    "yearBuilt": [
      1872,
      2010
    ],
    "overallQual": [
      1,
      10
    ],
    "bedrooms": [
      0,
      8
    ],
    "garageCars": [
      0,
      5
    ],
    "totalBsmtSF": [
      0,
      3206
    ],
    "lotArea": [
      1300,
      215245
    ],
    "fullBath": [
      0,
      4
    ]
  },
  "records": 2927,
  "model": {
    "mape": 0.0952,
    "r2": 0.8877,
    "sigma_log": 0.1366,
    "n": 2927
  }
}
```

## 3. Natural-language valuation (full multi-agent pipeline)

**`POST /api/v1/query`**

The main endpoint. Runs the complete state graph: Guardrail → Classifier → Retriever → Comp Analyst → Pricing Model → Valuer → Risk Analyst → Judge (with one retry on rejection). `filters` are hard metadata constraints applied before ranking. Blocked requests return `guardrails.passed = false` with empty results and no model call.

**Request format** — `QueryRequest`

| Field | Type | Notes |
|---|---|---|
| `query` | string | required; minLength 1, maxLength 2000 |
| `filters` | QueryFilters | optional |
| `top_k` | integer | optional; minimum 1, maximum 25 |

**Response format** — `QueryResponse` (`200 OK`)

| Field | Type | Notes |
|---|---|---|
| `requestId` | string |  |
| `mode` | string | optional; one of live, demo |
| `engine` | string | one of llm, rules, llm-degraded |
| `query` | string |  |
| `latencyMs` | integer |  |
| `guardrails` | GuardrailResult |  |
| `classification` | Classification or null | optional |
| `comparables` | array<Comparable> | optional |
| `valuation` | Valuation or null | optional |
| `prediction` | PricePrediction or null | optional |
| `judge` | JudgeVerdict or null | optional |
| `risk` | RiskAssessment or null | optional |
| `impact` | array<ImpactFactor> | optional |
| `agentTrace` | array<AgentStep> | optional |
| `answer` | string | optional |

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{"query": "3-bedroom in College Creek, 1,650 sq ft, built 1998, quality 7 — what is it worth?", "filters": {}, "top_k": 8}'
```

**Sample response** (`200`)

```json
{
  "requestId": "req_7456ff78b4",
  "mode": "live",
  "engine": "rules",
  "query": "3-bedroom in College Creek, 1,650 sq ft, built 1998, quality 7 — what is it worth?",
  "latencyMs": 149,
  "guardrails": {
    "passed": true,
    "checks": [
      {
        "name": "Length & encoding",
        "status": "pass",
        "detail": "16 tokens, NFKC-normalised"
      },
      {
        "name": "Prompt-injection scan",
        "status": "pass",
        "detail": "No instruction-override patterns detected"
      },
      "… 3 more"
    ]
  },
  "classification": {
    "intent": "valuation",
    "confidence": 0.9199999999999999,
    "propertyType": "unknown",
    "extractedAttributes": {
      "neighborhood": "CollgCr",
      "bedrooms": 3,
      "grLivArea": 1650,
      "yearBuilt": 1998,
      "overallQual": 7,
      "garageCars": null,
      "totalBsmtSF": null,
      "lotArea": null,
      "fullBath": null
    },
    "rationale": "Rule-based classification: intent 'valuation' from query verbs; extracted neighborhood, bedrooms, grLivArea, yearBuilt, overallQual via pattern matching."
  },
  "comparables": [
    {
      "property": {
        "id": "AMES-0843",
        "neighborhood": "CollgCr",
        "salePrice": 197900,
        "overallQual": 7,
        "overallCond": 5,
        "grLivArea": 1779,
        "totalBsmtSF": 866,
        "lotArea": 10400,
        "garageCars": 2,
        "garageArea": 546,
        "yearBuilt": 1998,
        "yearRemodAdd": 1998,
        "garageYrBlt": 1998,
        "fullBath": 2,
        "bedroomAbvGr": 3,
        "totRmsAbvGrd": 6,
        "saleYear": 2009,
        "bldgType": "OneFam",
        "summary": "3-bedroom, 2-bath single-family home in College Creek (CollgCr) with 1,779 sq ft of living area above grade, a 866 sq ft basement and a 2-car garage of 546 sq ft. Built in 1998; 11 years old at sale (mid-age). Overall quality 7/10, condition 5/10, 6 rooms total, on a 10,400 sq ft lot. Sold in 2009 for $197,900."
      },
      "semanticScore": 0.9134,
      "keywordScore": 0.9601,
      "hybridScore": 0.9301,
      "priorityScore": 0.9215,
      "priorityReasons": [
        "Same neighborhood",
        "Living area within 8%",
        "… 4 more"
      ],
      "adjustments": [
        {
          "label": "Living area",
          "amount": -7893
        },
        {
          "label": "Basement",
          "amount": 3432
        }
      ],
      "adjustedPrice": 193439
    },
    {
      "property": {
        "id": "AMES-0268",
        "neighborhood": "CollgCr",
        "salePrice": 224900,
        "overallQual": 7,
        "overallCond": 5,
        "grLivArea": 1661,
        "totalBsmtSF": 1649,
        "lotArea": 12137,
        "garageCars": 2,
        "garageArea": 598,
        "yearBuilt": 1998,
        "yearRemodAdd": 1998,
        "garageYrBlt": 1998,
        "fullBath": 2,
        "bedroomAbvGr": 3,
        "totRmsAbvGrd": 6,
        "saleYear": 2010,
        "bldgType": "OneFam",
        "summary": "3-bedroom, 2-bath single-family home in College Creek (CollgCr) with 1,661 sq ft of living area above grade, a 1,649 sq ft basement and a 2-car garage of 598 sq ft. Built in 1998; 12 years old at sale (mid-age). Overall quality 7/10, condition 5/10, 6 rooms total, on a 12,137 sq ft lot. Sold in 2010 for $224,900."
      },
      "semanticScore": 0.9101,
      "keywordScore": 0.9601,
      "hybridScore": 0.8452,
      "priorityScore": 0.9088,
      "priorityReasons": [
        "Same neighborhood",
        "Living area within 1%",
        "… 4 more"
      ],
      "adjustments": [
        {
          "label": "Living area",
          "amount": -819
        },
        {
          "label": "Basement",
          "amount": -6666
        }
      ],
      "adjustedPrice": 217415
    },
    "… 6 more"
  ],
  "valuation": {
    "estimate": 204000,
    "low": 181000,
    "high": 226500,
    "confidence": 0.779,
    "method": "ensemble",
    "pricePerSqft": 124,
    "narrative": "Weighted 8 prioritized comparables (8 in College Creek) after adjustments for living area, quality, age, garage and basement (comparable-weighted figure $205,000). The gradient-boosted model independently predicts $201,500; the ensemble gives 70% weight to comparables because neighborhood coverage is strong."
  },
  "prediction": {
    "model": "HistGradientBoosting · v1 (log-target, 5-fold CV)",
    "prediction": 201500,
    "low": 161000,
    "high": 252500,
    "mape": 0.0952,
    "r2": 0.8877,
    "featureContributions": [
      {
        "feature": "GrLivArea",
        "impact": 19762
      },
      {
        "feature": "Neighborhood",
        "impact": 10765
      },
      "… 6 more"
    ]
  },
  "judge": {
    "verdict": "approved",
    "score": 1.0,
    "criteria": [
      {
        "name": "Comparable relevance",
        "pass": true,
        "note": "8/8 comparables share the subject neighborhood"
      },
      {
        "name": "Model agreement",
        "pass": true,
        "note": "Ensemble vs. ML estimate differ by 1.2%"
      },
      "… 3 more"
    ],
    "summary": "Valuation is well-supported by in-neighborhood comparables and corroborated by the ML model."
  },
  "risk": {
    "level": "low",
    "score": 7,
    "drivers": [
      {
        "label": "Comparable dispersion",
        "weight": 9,
        "direction": "up"
      },
      {
        "label": "Neighborhood coverage",
        "weight": 8,
        "direction": "down"
      },
      "… 4 more"
    ],
    "volatility12m": 0.1561,
    "neighborhoodSales": 267
  },
  "impact": [
    {
      "feature": "OverallQual",
      "elasticity": 0.0818,
      "description": "Each quality point adds ~8.2% to expected price — the strongest single driver after location."
    },
    {
      "feature": "Neighborhood",
      "elasticity": 0.0115,
      "description": "College Creek carries a discount of 1% relative to the typical Ames neighborhood, holding size, age and quality constant."
    },
    "… 5 more"
  ],
  "agentTrace": [
    {
      "agent": "Guardrail",
      "role": "Input validation",
      "status": "done",
      "durationMs": 0,
      "output": "4 checks · intent in scope",
      "tool": "rules + regex"
    },
    {
      "agent": "Classifier",
      "role": "Intent & attribute extraction",
      "status": "done",
      "durationMs": 0,
      "output": "intent=valuation · {'neighborhood': 'CollgCr', 'bedrooms': 3, 'grLivArea': 1650, 'yearBuilt': 1998, 'overallQual': 7}",
      "tool": "llm:structured-output"
    },
    "… 6 more"
  ],
  "answer": "Based on 8 prioritized comparable sales, a 3-bedroom home of 1,650 sq ft in College Creek built around 1998 with quality grade 7 is estimated at $204,000 (range $181,000 – $226,500, $124/sq ft). The strongest comparable is AMES-0843, which sold for $197,900 in 2009 and adjusts to $193,439. The comparable-weighted and model estimates agree closely."
}
```

## 4. Hybrid property search

**`POST /api/v1/search`**

Retrieval only: BM25 ∪ FAISS dense search fused with reciprocal-rank fusion, after metadata filtering. Returns per-hit semantic, keyword and hybrid scores (all normalised to 0–1).

**Request format** — `SearchRequest`

| Field | Type | Notes |
|---|---|---|
| `query` | string | required; minLength 1, maxLength 2000 |
| `filters` | QueryFilters | optional |
| `top_k` | integer | optional; minimum 1, maximum 50 |

**Response format** — `SearchResponse` (`200 OK`)

| Field | Type | Notes |
|---|---|---|
| `query` | string |  |
| `total_candidates` | integer |  |
| `hits` | array<SearchHit> |  |

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/search' \
  -H 'Content-Type: application/json' \
  -d '{"query": "Northridge Heights 4 bedroom 3-car garage", "filters": {"minYearBuilt": 2000}, "top_k": 3}'
```

**Sample response** (`200`)

```json
{
  "query": "Northridge Heights 4 bedroom 3-car garage",
  "total_candidates": 780,
  "hits": [
    {
      "property": {
        "id": "AMES-0422",
        "neighborhood": "NridgHt",
        "salePrice": 462000,
        "overallQual": 9,
        "overallCond": 5,
        "grLivArea": 2772,
        "totalBsmtSF": 1776,
        "lotArea": 14257,
        "garageCars": 3,
        "garageArea": 754,
        "yearBuilt": 2007,
        "yearRemodAdd": 2007,
        "garageYrBlt": 2007,
        "fullBath": 3,
        "bedroomAbvGr": 4,
        "totRmsAbvGrd": 10,
        "saleYear": 2009,
        "bldgType": "OneFam",
        "summary": "4-bedroom, 3-bath single-family home in Northridge Heights (NridgHt) with 2,772 sq ft of living area above grade, a 1,776 sq ft basement and a 3-car garage of 754 sq ft. Built in 2007; 2 years old at sale (new construction). Overall quality 9/10, condition 5/10, 10 rooms total, on a 14,257 sq ft lot. Sold in 2009 for $462,000."
      },
      "semanticScore": 0.9165,
      "keywordScore": 1.0,
      "hybridScore": 1.0
    },
    {
      "property": {
        "id": "AMES-0450",
        "neighborhood": "NridgHt",
        "salePrice": 290000,
        "overallQual": 8,
        "overallCond": 5,
        "grLivArea": 2400,
        "totalBsmtSF": 1082,
        "lotArea": 13262,
        "garageCars": 3,
        "garageArea": 730,
        "yearBuilt": 2003,
        "yearRemodAdd": 2004,
        "garageYrBlt": 2003,
        "fullBath": 3,
        "bedroomAbvGr": 4,
        "totRmsAbvGrd": 10,
        "saleYear": 2009,
        "bldgType": "OneFam",
        "summary": "4-bedroom, 3-bath single-family home in Northridge Heights (NridgHt) with 2,400 sq ft of living area above grade, a 1,082 sq ft basement and a 3-car garage of 730 sq ft. Built in 2003, remodeled in 2004; 6 years old at sale (recently built). Overall quality 8/10, condition 5/10, 10 rooms total, on a 13,262 sq ft lot. Sold in 2009 for $290,000."
      },
      "semanticScore": 0.9196,
      "keywordScore": 0.9859,
      "hybridScore": 0.9806
    },
    "… 1 more"
  ]
}
```

## 5. Property / intent classification

**`POST /api/v1/classify`**

Runs the Classifier agent alone: intent (`valuation`, `similar_properties`, `comparison`, `price_difference`, `market_insight`, `out_of_scope`), property type and extracted attributes.

**Request format** — `SearchRequest`

| Field | Type | Notes |
|---|---|---|
| `query` | string | required; minLength 1, maxLength 2000 |
| `filters` | QueryFilters | optional |
| `top_k` | integer | optional; minimum 1, maximum 50 |

**Response format** — JSON object (`200 OK`) with keys: `engine`, `intent`, `confidence`, `propertyType`, `extractedAttributes`, `rationale`

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/classify' \
  -H 'Content-Type: application/json' \
  -d '{"query": "Why would a 2,000 sq ft Somerset house be worth more than a similar one in Gilbert?"}'
```

**Sample response** (`200`)

```json
{
  "engine": "rules",
  "intent": "price_difference",
  "confidence": 0.7999999999999999,
  "propertyType": "single_family",
  "extractedAttributes": {
    "neighborhood": "Somerst",
    "bedrooms": null,
    "grLivArea": 2000,
    "yearBuilt": null,
    "overallQual": null,
    "garageCars": null,
    "totalBsmtSF": null,
    "lotArea": null,
    "fullBath": null
  },
  "rationale": "Rule-based classification: intent 'price_difference' from query verbs; extracted neighborhood, grLivArea via pattern matching."
}
```

## 6. Valuation from explicit attributes

**`POST /api/v1/valuation`**

Skips natural-language parsing: the caller supplies the subject's attributes directly. Returns comparables, valuation, ML prediction and judge verdict. Unknown neighborhood codes and negative values return 422.

**Request format** — `ValuationRequest`

| Field | Type | Notes |
|---|---|---|
| `neighborhood` | string or null | optional |
| `bedrooms` | integer or null | optional |
| `grLivArea` | integer or null | optional |
| `yearBuilt` | integer or null | optional |
| `overallQual` | integer or null | optional |
| `garageCars` | integer or null | optional |
| `totalBsmtSF` | integer or null | optional |
| `lotArea` | integer or null | optional |
| `fullBath` | integer or null | optional |
| `top_k` | integer | optional; minimum 1, maximum 25 |

**Response format** — JSON object (`200 OK`) with keys: `subject`, `valuation`, `prediction`, `judge`, `comparables`, `answer`

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/valuation' \
  -H 'Content-Type: application/json' \
  -d '{"neighborhood": "Somerst", "grLivArea": 2000, "yearBuilt": 2005, "overallQual": 8, "bedrooms": 4, "garageCars": 2, "top_k": 3}'
```

**Sample response** (`200`)

```json
{
  "subject": {
    "neighborhood": "Somerst",
    "bedrooms": 4,
    "grLivArea": 2000,
    "yearBuilt": 2005,
    "overallQual": 8,
    "garageCars": 2,
    "totalBsmtSF": 1400,
    "lotArea": 9000,
    "fullBath": 2
  },
  "valuation": {
    "estimate": 273500,
    "low": 233500,
    "high": 313000,
    "confidence": 0.584,
    "method": "ensemble",
    "pricePerSqft": 137,
    "narrative": "Weighted 3 prioritized comparables (3 in Somerset) after adjustments for living area, quality, age, garage and basement (comparable-weighted figure $263,000). The gradient-boosted model independently predicts $288,000; the ensemble gives 59% weight to comparables because neighborhood coverage is strong."
  },
  "prediction": {
    "model": "HistGradientBoosting · v1 (log-target, 5-fold CV)",
    "prediction": 288000,
    "low": 230000,
    "high": 360500,
    "mape": 0.0952,
    "r2": 0.8877,
    "featureContributions": [
      {
        "feature": "GrLivArea",
        "impact": 75302
      },
      {
        "feature": "OverallQual",
        "impact": 42374
      },
      "… 6 more"
    ]
  },
  "judge": {
    "verdict": "approved",
    "score": 1.0,
    "criteria": [
      {
        "name": "Comparable relevance",
        "pass": true,
        "note": "3/3 comparables share the subject neighborhood"
      },
      {
        "name": "Model agreement",
        "pass": true,
        "note": "Ensemble vs. ML estimate differ by 5.3%"
      },
      "… 3 more"
    ],
    "summary": "Valuation is well-supported by in-neighborhood comparables and corroborated by the ML model."
  },
  "comparables": [
    {
      "property": {
        "id": "AMES-0386",
        "neighborhood": "Somerst",
        "salePrice": 220000,
        "overallQual": 8,
        "overallCond": 5,
        "grLivArea": 1874,
        "totalBsmtSF": 1058,
        "lotArea": 7500,
        "garageCars": 2,
        "garageArea": 588,
        "yearBuilt": 2000,
        "yearRemodAdd": 2001,
        "garageYrBlt": 2000,
        "fullBath": 2,
        "bedroomAbvGr": 3,
        "totRmsAbvGrd": 7,
        "saleYear": 2009,
        "bldgType": "OneFam",
        "summary": "3-bedroom, 2-bath single-family home in Somerset (Somerst) with 1,874 sq ft of living area above grade, a 1,058 sq ft basement and a 2-car garage of 588 sq ft. Built in 2000, remodeled in 2001; 9 years old at sale (recently built). Overall quality 8/10, condition 5/10, 7 rooms total, on a 7,500 sq ft lot. Sold in 2009 for $220,000."
      },
      "semanticScore": 0.9306,
      "keywordScore": 0.9879,
      "hybridScore": 0.8405,
      "priorityScore": 0.8571,
      "priorityReasons": [
        "Same neighborhood",
        "Living area within 6%",
        "… 3 more"
      ],
      "adjustments": [
        {
          "label": "Living area",
          "amount": 8136
        },
        {
          "label": "Age",
          "amount": 2750
        },
        "… 1 more"
      ],
      "adjustedPrice": 235400
    },
    {
      "property": {
        "id": "AMES-0106",
        "neighborhood": "Somerst",
        "salePrice": 254000,
        "overallQual": 8,
        "overallCond": 5,
        "grLivArea": 1848,
        "totalBsmtSF": 975,
        "lotArea": 7379,
        "garageCars": 2,
        "garageArea": 592,
        "yearBuilt": 2000,
        "yearRemodAdd": 2000,
        "garageYrBlt": 2000,
        "fullBath": 2,
        "bedroomAbvGr": 3,
        "totRmsAbvGrd": 7,
        "saleYear": 2010,
        "bldgType": "OneFam",
        "summary": "3-bedroom, 2-bath single-family home in Somerset (Somerst) with 1,848 sq ft of living area above grade, a 975 sq ft basement and a 2-car garage of 592 sq ft. Built in 2000; 10 years old at sale (recently built). Overall quality 8/10, condition 5/10, 7 rooms total, on a 7,379 sq ft lot. Sold in 2010 for $254,000."
      },
      "semanticScore": 0.9282,
      "keywordScore": 0.9966,
      "hybridScore": 0.8177,
      "priorityScore": 0.8537,
      "priorityReasons": [
        "Same neighborhood",
        "Living area within 8%",
        "… 3 more"
      ],
      "adjustments": [
        {
          "label": "Living area",
          "amount": 11490
        },
        {
          "label": "Age",
          "amount": 3175
        },
        "… 1 more"
      ],
      "adjustedPrice": 275142
    },
    "… 1 more"
  ],
  "answer": "Based on 3 prioritized comparable sales, a 4-bedroom home of 2,000 sq ft in Somerset built around 2005 with quality grade 8 is estimated at $273,500 (range $233,500 – $313,000, $137/sq ft). The strongest comparable is AMES-0386, which sold for $220,000 in 2009 and adjusts to $235,400. The two methods differ by 9%, so the range is widened accordingly."
}
```

## 7. ML price prediction

**`POST /api/v1/predict`**

Gradient-boosted model only: point prediction, 90 % interval and per-feature contributions (single-feature substitution against the median).

**Request format** — `PredictRequest`

| Field | Type | Notes |
|---|---|---|
| `neighborhood` | string or null | optional |
| `bedrooms` | integer or null | optional |
| `grLivArea` | integer or null | optional |
| `yearBuilt` | integer or null | optional |
| `overallQual` | integer or null | optional |
| `garageCars` | integer or null | optional |
| `totalBsmtSF` | integer or null | optional |
| `lotArea` | integer or null | optional |
| `fullBath` | integer or null | optional |

**Response format** — `PricePrediction` (`200 OK`)

| Field | Type | Notes |
|---|---|---|
| `model` | string |  |
| `prediction` | integer |  |
| `low` | integer |  |
| `high` | integer |  |
| `mape` | number |  |
| `r2` | number |  |
| `featureContributions` | array<FeatureContribution> |  |

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/predict' \
  -H 'Content-Type: application/json' \
  -d '{"neighborhood": "Somerst", "grLivArea": 2000, "yearBuilt": 2005, "overallQual": 8, "bedrooms": 4, "garageCars": 2}'
```

**Sample response** (`200`)

```json
{
  "model": "HistGradientBoosting · v1 (log-target, 5-fold CV)",
  "prediction": 288000,
  "low": 230000,
  "high": 360500,
  "mape": 0.0952,
  "r2": 0.8877,
  "featureContributions": [
    {
      "feature": "GrLivArea",
      "impact": 75302
    },
    {
      "feature": "OverallQual",
      "impact": 42374
    },
    "… 6 more"
  ]
}
```

## 8. Explain a price difference between two records

**`POST /api/v1/compare`**

Feature and location impact analysis. The hedonic model attributes the sale-price gap between record `a` and record `b` to neighborhood, living area, quality, age, garage, basement and condition, and reports the unexplained remainder. Unknown ids return 404.

**Request format** — `CompareRequest`

| Field | Type | Notes |
|---|---|---|
| `a` | string | required |
| `b` | string | required |

**Response format** — `CompareResponse` (`200 OK`)

| Field | Type | Notes |
|---|---|---|
| `a` | Property |  |
| `b` | Property |  |
| `difference` | integer |  |
| `factors` | array<CompareFactor> |  |
| `explainedShare` | number |  |
| `narrative` | string |  |

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/compare' \
  -H 'Content-Type: application/json' \
  -d '{"a": "AMES-0001", "b": "AMES-0002"}'
```

**Sample response** (`200`)

```json
{
  "a": {
    "id": "AMES-0001",
    "neighborhood": "NAmes",
    "salePrice": 215000,
    "overallQual": 6,
    "overallCond": 5,
    "grLivArea": 1656,
    "totalBsmtSF": 1080,
    "lotArea": 31770,
    "garageCars": 2,
    "garageArea": 528,
    "yearBuilt": 1960,
    "yearRemodAdd": 1960,
    "garageYrBlt": 1960,
    "fullBath": 1,
    "bedroomAbvGr": 3,
    "totRmsAbvGrd": 7,
    "saleYear": 2010,
    "bldgType": "OneFam",
    "summary": "3-bedroom, 1-bath single-family home in North Ames (NAmes) with 1,656 sq ft of living area above grade, a 1,080 sq ft basement and a 2-car garage of 528 sq ft. Built in 1960; 50 years old at sale (older). Overall quality 6/10, condition 5/10, 7 rooms total, on a 31,770 sq ft lot. Sold in 2010 for $215,000."
  },
  "b": {
    "id": "AMES-0002",
    "neighborhood": "NAmes",
    "salePrice": 105000,
    "overallQual": 5,
    "overallCond": 6,
    "grLivArea": 896,
    "totalBsmtSF": 882,
    "lotArea": 11622,
    "garageCars": 1,
    "garageArea": 730,
    "yearBuilt": 1961,
    "yearRemodAdd": 1961,
    "garageYrBlt": 1961,
    "fullBath": 1,
    "bedroomAbvGr": 2,
    "totRmsAbvGrd": 5,
    "saleYear": 2010,
    "bldgType": "OneFam",
    "summary": "2-bedroom, 1-bath single-family home in North Ames (NAmes) with 896 sq ft of living area above grade, a 882 sq ft basement and a 1-car garage of 730 sq ft. Built in 1961; 49 years old at sale (older). Overall quality 5/10, condition 6/10, 5 rooms total, on a 11,622 sq ft lot. Sold in 2010 for $105,000."
  },
  "difference": -110000,
  "factors": [
    {
      "label": "Unexplained / market noise",
      "amount": -62879,
      "why": "Timing, lot shape, sale type, interior finish and other unmodelled attributes"
    },
    {
      "label": "Living area",
      "amount": -34857,
      "why": "896 vs 1,656 sq ft"
    },
    "… 6 more"
  ],
  "explainedShare": 0.428,
  "narrative": "AMES-0002 sold for $110,000 less than AMES-0001. The hedonic model attributes most of the gap to living area (-34,857) and quality grade (-12,104); 43% of the difference is explained by measurable attributes."
}
```

## 9. Browse / filter records

**`POST /api/v1/properties`**

Metadata filtering over the full record set. Body is a `QueryFilters` object; `limit` and `offset` are query parameters for paging.

**Query parameters**

| Name | Type | Default |
|---|---|---|
| `limit` | integer | 3000 |
| `offset` | integer | 0 |

**Request format** — `QueryFilters`

| Field | Type | Notes |
|---|---|---|
| `neighborhoods` | array or null | optional |
| `minYearBuilt` | integer or null | optional; minimum 1800, maximum 2100 |
| `maxYearBuilt` | integer or null | optional; minimum 1800, maximum 2100 |
| `minBedrooms` | integer or null | optional; minimum 0, maximum 20 |
| `maxBedrooms` | integer or null | optional; minimum 0, maximum 20 |
| `minGrLivArea` | integer or null | optional; minimum 0, maximum 20000 |
| `maxGrLivArea` | integer or null | optional; minimum 0, maximum 20000 |
| `minQual` | integer or null | optional; minimum 1, maximum 10 |
| `maxPrice` | integer or null | optional; minimum 0 |

**Response format** — `PropertiesResponse` (`200 OK`)

| Field | Type | Notes |
|---|---|---|
| `items` | array<Property> |  |
| `total` | integer |  |

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/properties?limit=2&offset=0' \
  -H 'Content-Type: application/json' \
  -d '{"neighborhoods": ["Veenker"], "minYearBuilt": 1990}'
```

**Sample response** (`200`)

```json
{
  "items": [
    {
      "id": "AMES-1179",
      "neighborhood": "Veenker",
      "salePrice": 245500,
      "overallQual": 8,
      "overallCond": 5,
      "grLivArea": 1288,
      "totalBsmtSF": 1260,
      "lotArea": 14963,
      "garageCars": 2,
      "garageArea": 500,
      "yearBuilt": 1996,
      "yearRemodAdd": 1996,
      "garageYrBlt": 1996,
      "fullBath": 1,
      "bedroomAbvGr": 1,
      "totRmsAbvGrd": 4,
      "saleYear": 2008,
      "bldgType": "TwnhsE",
      "summary": "1-bedroom, 1-bath townhouse in Veenker (Veenker) with 1,288 sq ft of living area above grade, a 1,260 sq ft basement and a 2-car garage of 500 sq ft. Built in 1996; 12 years old at sale (mid-age). Overall quality 8/10, condition 5/10, 4 rooms total, on a 14,963 sq ft lot. Sold in 2008 for $245,500."
    },
    {
      "id": "AMES-1180",
      "neighborhood": "Veenker",
      "salePrice": 217500,
      "overallQual": 8,
      "overallCond": 5,
      "grLivArea": 1239,
      "totalBsmtSF": 1230,
      "lotArea": 11064,
      "garageCars": 2,
      "garageArea": 477,
      "yearBuilt": 1995,
      "yearRemodAdd": 1995,
      "garageYrBlt": 1995,
      "fullBath": 1,
      "bedroomAbvGr": 1,
      "totRmsAbvGrd": 4,
      "saleYear": 2008,
      "bldgType": "TwnhsE",
      "summary": "1-bedroom, 1-bath townhouse in Veenker (Veenker) with 1,239 sq ft of living area above grade, a 1,230 sq ft basement and a 2-car garage of 477 sq ft. Built in 1995; 13 years old at sale (mid-age). Overall quality 8/10, condition 5/10, 4 rooms total, on a 11,064 sq ft lot. Sold in 2008 for $217,500."
    }
  ],
  "total": 6
}
```

## 10. Submit feedback (continuous-improvement loop)

**`POST /api/v1/feedback`**

Thumbs up/down, an optional corrected value and comment, joined to the original request by `requestId`. Corrected values automatically become evaluation cases in the next eval run.

**Request format** — `FeedbackPayload`

| Field | Type | Notes |
|---|---|---|
| `requestId` | string | required |
| `rating` | string | required; one of up, down |
| `correctedValue` | integer or null | optional; minimum 1000, maximum 5000000 |
| `comment` | string or null | optional |

**Response format** — JSON object (`200 OK`) with keys: `ok`, `linked`, `query`, `estimate`, `counts`

**Sample request**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/feedback' \
  -H 'Content-Type: application/json' \
  -d '{"requestId": "req_7456ff78b4", "rating": "down", "correctedValue": 215000, "comment": "Recent College Creek sales are higher"}'
```

**Sample response** (`200`)

```json
{
  "ok": true,
  "linked": true,
  "query": "3-bedroom in College Creek, 1,650 sq ft, built 1998, quality 7 — what is it worth?",
  "estimate": 204000,
  "counts": {
    "positive": 0,
    "negative": 1,
    "corrected": 1
  }
}
```

## 11. Latest evaluation results

**`GET /api/v1/evaluation/latest`**

Metrics, thresholds and pass rates from the most recent evaluation run, trend history, judge agreement, feedback counts and live latency percentiles. Backs the Evaluation dashboard.

**Request format** — no body

**Response format** — `EvalSummary` (`200 OK`)

| Field | Type | Notes |
|---|---|---|
| `runId` | string |  |
| `ranAt` | string |  |
| `cases` | integer |  |
| `metrics` | array<EvalMetric> |  |
| `judgeAgreement` | number |  |
| `history` | array<EvalHistoryPoint> |  |
| `feedback` | EvalFeedback |  |
| `latencyP50` | integer |  |
| `latencyP95` | integer |  |
| `source` | string | optional |

**Sample request**

```bash
curl -s -X GET 'http://localhost:8000/api/v1/evaluation/latest'
```

**Sample response** (`200`)

```json
{
  "runId": "eval_2026-10-08_1517",
  "ranAt": "2026-10-08T15:17:59.352075+00:00",
  "cases": 61,
  "metrics": [
    {
      "name": "Faithfulness",
      "score": 1.0,
      "threshold": 0.85,
      "passRate": 1.0
    },
    {
      "name": "Answer relevancy",
      "score": 0.9821,
      "threshold": 0.8,
      "passRate": 0.9821
    },
    "… 7 more"
  ],
  "judgeAgreement": 0.7111,
  "history": [
    {
      "date": "Oct 07",
      "faithfulness": 1.0,
      "relevancy": 0.982,
      "precision": 0.868
    },
    {
      "date": "Oct 08",
      "faithfulness": 1.0,
      "relevancy": 0.982,
      "precision": 0.873
    },
    "… 2 more"
  ],
  "feedback": {
    "positive": 0,
    "negative": 1,
    "corrected": 1
  },
  "latencyP50": 149,
  "latencyP95": 149,
  "source": "builtin"
}
```

## Error responses

**Validation error** — `POST /api/v1/query` with an empty query:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": [
        "body",
        "query"
      ],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {
        "min_length": 1
      }
    }
  ]
}
```

**Not found** — `POST /api/v1/compare` with an unknown id (problem details):

```json
{
  "type": "about:blank",
  "title": "Unknown record id",
  "status": 404,
  "detail": "Unknown record id"
}
```

**Guardrail block** — `POST /api/v1/query` with a prompt-injection attempt returns `200` with `guardrails.passed = false`, no comparables and no model call:

```json
{
  "guardrails": {
    "passed": false,
    "checks": [
      {
        "name": "Length & encoding",
        "status": "pass",
        "detail": "8 tokens, NFKC-normalised"
      },
      {
        "name": "Prompt-injection scan",
        "status": "fail",
        "detail": "Instruction-override pattern detected"
      },
      {
        "name": "PII redaction",
        "status": "pass",
        "detail": "No personal identifiers present"
      },
      {
        "name": "Domain relevance",
        "status": "fail",
        "detail": "Query is outside real-estate valuation scope"
      }
    ]
  },
  "comparables": [],
  "valuation": null,
  "answer": "The request was blocked by input guardrails before any retrieval or model call. Rephrase it as a property description or valuation question."
}
```
