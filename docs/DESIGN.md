# Valora — Design decisions and trade-offs

This document explains *why* the system is shaped the way it is. The
architecture diagram is in `docs/architecture.pdf` / `.jpg`.

## 1. Problem framing

Real-estate professionals ask three kinds of questions: *what sold that is like
this?*, *why do two similar homes differ in price?*, and *what is this worth?*.
All three need the same evidence — the most comparable historical sales — and
differ only in what is computed on top. The system is therefore built as one
retrieval core with a small set of specialised agents on top of it, rather than
three separate features.

## 2. Data representation

| Decision | Rationale | Trade-off |
|---|---|---|
| Convert every tabular record into a **natural-language "property case"** (`loader.describe`) and index *that* | Dense embedding models are trained on prose, not column vectors. A sentence like "3-bedroom single-family home in College Creek (CollgCr) with 1,650 sq ft… built in 1998" embeds close to how users phrase queries. The text deliberately contains both the neighborhood code and full name, the age in years and an era word ("recently built"), because those are what people type. | One-off cost at index time; the text template is a tuning surface. |
| Keep the **numeric frame** alongside the text | Filtering, adjustments and the ML model need exact numbers; parsing them back out of text would be fragile. | Two representations to keep aligned (done once in the loader). |
| Map OpenML's long labels to canonical Ames codes (`North_Ames → NAmes`) and quality words to 1–10 | Matches the literature, the UI and user vocabulary. | None material. |
| Drop the 3 partial-sale outliers (>4,000 sq ft, <$300k) | Recommended by the dataset author; they distort both comps and the regressor. | 2,927 of 2,930 rows are used. |

## 3. Retrieval

| Decision | Rationale | Trade-off |
|---|---|---|
| **Hybrid BM25 + dense** fused with **reciprocal-rank fusion** | Queries mix exact tokens (`NridgHt`, `1998`, `3-car`) that BM25 nails with semantic phrasing ("recently built ranch") that only embeddings capture. RRF needs no score calibration between the two systems. | Two indexes to keep in sync (both built from the same list in one pass). |
| Dense model: **fastembed / bge-small-en-v1.5** (ONNX, 384-d) with **LSA fallback** | A real neural encoder that runs on CPU without PyTorch, ~130 MB RAM. If the model cannot be downloaded (air-gapped CI, Render cold start failure) the index silently falls back to TF-IDF→SVD so the service still starts. `/health` reports which one is active. | Slightly lower recall than large encoders; acceptable at 2.9k docs. |
| **numpy matrix as the vector store** | 2,927 × 384 floats is 4.5 MB. Exact cosine search runs in <1 ms. A vector database would add a network hop, an ops burden and no retrieval benefit at this scale. The `HybridIndex` class is the single swap point for pgvector/Qdrant if the corpus grows 100×. | Not horizontally shareable across processes; fine for one container. |
| **Metadata filters are hard constraints applied before ranking** | A user who says "built before 1940" must never see a 2005 home. Filtering first also keeps the top-k budget for real candidates. | A tight filter can starve retrieval; the response shows the surviving pool size so the user can see why results are thin. |

## 4. Comparable prioritization and valuation

| Decision | Rationale | Trade-off |
|---|---|---|
| Separate **retrieval similarity** from **comparable priority** | Text similarity is not appraisal comparability. The Comp Analyst re-scores candidates on the criteria an appraiser uses (same neighborhood, ±10 % living area, ±8 years, same quality grade, recent sale) and exposes every reason. | Two scores to explain; the UI shows both. |
| **Appraisal-style adjustments** per comp | Standard practice: adjust each comp's price toward the subject, then weight. It makes the estimate auditable line by line. Adjustment rates come from the hedonic fit (≈5.5 %/quality point, 0.25 %/year…). | Linear adjustments are an approximation; they are capped at ±30 % and the judge checks them. |
| **Ensemble** of comparable-weighted estimate and gradient-boosted model | Two independent methods; their divergence is itself a risk signal. Comps get more weight when in-neighborhood coverage is strong and dispersion is low (`w_comp ∈ [0.25, 0.75]`). | Needs a trained model artifact (trained in ~2 s at startup and cached by data hash). |
| **Pricing model: HistGradientBoosting on log(price)**, metrics from **5-fold CV**, not the training fit | Log target makes errors multiplicative, which is how prices behave. Hold-out MAPE 9.5 %, R² 0.89 are honest numbers. | No SHAP dependency — feature contributions use single-feature substitution against the median ("SHAP-lite"), cheap and model-agnostic. |
| **Hedonic OLS** for elasticities and neighborhood premiums | A log-linear regression with neighborhood fixed effects gives interpretable, quotable coefficients ("each quality point ≈ +X %") and a principled way to explain price gaps between two records (`/compare`). | Linear-in-logs; interactions are left to the boosted model. |

## 5. Agents and the LLM

| Decision | Rationale | Trade-off |
|---|---|---|
| A **hand-written typed state graph** (`graph.py`) instead of an agent framework | Eight nodes, one conditional edge, full trace — ~120 lines that every reviewer can read. No framework version churn, no hidden prompts, deterministic apart from the LLM calls. | We re-implement a tiny subset of what LangGraph offers; acceptable at this size. |
| **The LLM never produces a number.** It classifies, phrases, and judges; code computes. | Hallucinated figures are the single biggest risk in a valuation product. Narratives are generated from the computed numbers and the judge verifies every figure in the answer traces to evidence. | The prose is sometimes less fluent in rules mode. |
| **Structured outputs** (Pydantic schemas via `messages.parse`) for every LLM call, with a **self-healing JSON-by-instruction fallback** | No prose parsing between agents. If the provider is an API gateway that strips `output_config` (observed with aicredits.in), the wrapper detects the first non-JSON reply, switches to embedding the JSON Schema in the system prompt, extracts the first balanced object, validates it and makes one repair call on failure. | Native mode is stricter; the fallback adds ~40 tokens of schema to each prompt. |
| **Provider-agnostic configuration** (`ANTHROPIC_BASE_URL`, `LLM_MODEL`, `LLM_FALLBACK_MODEL`) | The same code runs against api.anthropic.com or an Anthropic-compatible gateway; model ids are whatever the provider exposes. | Gateways may lag on newest models; we pin Sonnet 4.6 → Haiku 4.5 on the current one. |
| **Every LLM call has a rule-based fallback** and the response reports `engine: llm | llm-degraded | rules` | The service must work in CI, in demos without a key, and during provider outages. The wrapper tries primary → fallback model → rules, with a timeout and one retry, and a **circuit breaker**: a billing/auth error (402/403) or four consecutive failures opens the circuit for 60 s so requests stop paying the failed-call latency and go straight to rules. `/health` exposes `lastError` and `circuitOpenForS`; the UI shows them. | Three code paths to test; the built-in eval runs the rules path on every CI run. |
| **LLM-as-judge is a separate prompt that sees only evidence** and is bounded by deterministic checks | Independence from the generator. The judge cannot approve a narrative that cites an ungrounded figure, and cannot be more generous than the numeric pre-checks allow (its score is averaged with them). | +1 LLM call (~1 s). |
| **Judge retry loop**: a rejection triggers one second pass with a doubled candidate pool | The most common cause of rejection is thin comparable coverage; widening the pool is the right remedy and makes the "collaboration" real rather than linear. | Bounded to one retry to cap latency. |

## 6. Guardrails

Input: NFKC normalisation and control-character stripping, length bounds,
prompt-injection pattern scan, PII redaction (email/phone/SSN) before the text
reaches any model, domain-relevance lexicon, and clamping of extracted
attributes to the dataset's observed range (reported as a warning, not an
error). The classifier adds a semantic gate (`out_of_scope`). Output: Pydantic
schema validation and the judge.

## 7. Evaluation strategy

Three layers, each answering a different question:

1. **Built-in eval (CI, no key)** — *does the system work?* 60 golden cases:
   44 hold-out valuations generated from real records (the record is excluded
   from its own comparables), 11 intent/retrieval cases, 5 guardrail cases, plus
   any human-corrected cases from the feedback table. Metrics: contextual
   precision/recall of comps, valuation MAPE and range coverage, groundedness
   (every figure in the answer traces to evidence), intent and guardrail
   accuracy, judge agreement, latency. Thresholds gate the run (exit code 1).
2. **DeepEval (LLM-graded)** — *is the recommendation good?* The same cases
   as `LLMTestCase`s with the retrieved comparables as `retrieval_context`,
   scored by Faithfulness, Answer Relevancy, Contextual Precision/Recall and
   Hallucination with Claude as grader, plus a custom `ValuationMAPE` metric.
3. **Online judge + human feedback** — *is this specific answer good?* Every
   response is judged; reviewers rate and correct; corrections become labelled
   eval cases automatically.

## 8. API and operations

FastAPI with Pydantic validation on every request, RFC 9457 problem-details
errors, a per-IP sliding-window rate limiter, strict CORS (explicit origins +
`*.vercel.app`), `/health` with dependency status and latency percentiles,
and request logging to SQLite keyed by `requestId`. Secrets come only from the
environment. The Docker image warms every cache at build time (embedding model
download, corpus embedding, model training) so the first request on Render is
fast and the service starts even if the network is restricted at runtime.

## 9. Frontend

Next.js 16 on Vercel. The API client has a 20 s timeout and falls back to a
deterministic demo dataset when the backend is unreachable; the UI labels the
mode and the engine honestly. Contracts live in one file (`types.ts`) that the
backend schemas mirror field-for-field, so the UI switches from demo to live
without code changes.

## 10. Model selection under a budget

The LLM does three narrow jobs per query (classification, phrasing, judging), each
with short prompts (~1–1.6k tokens). That shape favours a fast, cheap model: Haiku 4.5
handles structured extraction and short grounded prose reliably and costs ≈ ₹0.54 per
query on the gateway (≈ 90 queries for ₹50). Sonnet-class models write noticeably
better judge notes but triple the cost and latency; they are the right choice for the
judge step only when budget allows. Model ids per step live in environment variables
so this can change without a deploy, and both the Anthropic Messages format and
OpenAI-style chat completions are supported because gateways expose different models
on each.

## 11. What I would do next

- Stream the agent trace over Server-Sent Events so users see each node finish.
- Add a "confidence too low → ask a clarifying question" branch before the valuer.
- Replace single-feature substitution with SHAP once the dependency footprint is acceptable.
- Nightly DeepEval run on Render cron with a regression alert.
- Time-adjust comparables to the subject's sale date (currently only "recent sale" bonus).
