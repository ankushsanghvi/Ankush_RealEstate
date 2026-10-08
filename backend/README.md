# Valora API (backend)

FastAPI microservice: hybrid retrieval + multi-agent valuation over the Ames Housing dataset.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY to enable the LLM engine (optional)
uvicorn app.main:app --reload --port 8000
# OpenAPI docs: http://localhost:8000/docs
```

First start downloads the embedding model (~35 MB), embeds 2,927 property cases (~30 s)
and trains the pricing model (~2 s); all three are cached under `data/cache/`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/query` | Full pipeline: guardrails → classify → hybrid retrieve → prioritize → predict → value → risk → judge |
| POST | `/api/v1/search` | Hybrid search only, with metadata filters and both score components |
| POST | `/api/v1/classify` | Classification agent (intent, property type, attributes) |
| POST | `/api/v1/valuation` | Valuation from explicit attributes |
| POST | `/api/v1/predict` | ML price prediction with feature contributions |
| POST | `/api/v1/compare` | Explain the price gap between two record ids |
| POST | `/api/v1/properties` | Filter/page the indexed records |
| POST | `/api/v1/feedback` | Record rating / corrected value / comment against a request id |
| GET | `/api/v1/evaluation/latest` | Latest eval run + live feedback counts and latency |
| GET | `/api/v1/meta` | Neighborhood stats, attribute bounds, model metrics |
| GET | `/health` | Liveness, engine, embedding backend, LLM status, latency percentiles |

## Tests and evaluation

```bash
pip install -r requirements-eval.txt
pytest -q                               # 44 tests (API, edge cases, guardrails, vector store, LLM wrapper)
python evals/build_golden_set.py        # regenerate the 60-case golden set (deterministic seed)
python evals/run_eval.py                # built-in metrics, no key; exit 1 on threshold regression
python evals/benchmark_embeddings.py    # compare 4 embedding models on the golden set, no key
python evals/run_deepeval.py 10         # DeepEval LLM-graded suite, first 10 cases (needs ANTHROPIC_API_KEY)
```

## Layout

```
app/
  main.py          FastAPI app, middleware, endpoints
  graph.py         typed state graph: nodes, edges, judge retry loop, tracing
  services.py      startup singletons (dataset, index, models, LLM, feedback store)
  schemas.py       Pydantic contracts (mirror frontend/src/lib/types.ts)
  config.py        env-driven settings
  data/loader.py   ARFF → typed records + NL property cases + neighborhood stats
  retrieval/       embedder (fastembed | LSA), FAISS vector store, hybrid index (BM25 ∪ dense, RRF, filters)
  agents/          llm, guardrails, classifier, comparables, pricing, impact, risk, valuer, judge
  feedback.py      SQLite request log + feedback + corrected cases
  evaluation.py    serves evals/results/latest.json
evals/             golden set builder, built-in runner, embedding benchmark, DeepEval runner, results/
tests/             pytest suite (API, edge cases)
Dockerfile, render.yaml
```
