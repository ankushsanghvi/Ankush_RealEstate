"""Valora API — FastAPI microservice exposing the valuation pipeline."""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.agents.classifier import classify
from app.agents.comparables import Subject, prioritize
from app.agents.judge import judge
from app.agents.valuer import ensemble, write_narrative
from app.config import get_settings
from app.data.loader import NEIGHBORHOOD_NAMES, apply_filters
from app.evaluation import load_latest
from app.graph import run_pipeline
from app.schemas import (
    CompareFactor, CompareRequest, CompareResponse, EvalSummary, FeedbackPayload, Health, PredictRequest, PricePrediction, PropertiesResponse,
    QueryFilters, QueryRequest, QueryResponse, SearchHit, SearchRequest, SearchResponse, SubjectAttributes, ValuationRequest,
)
from app.services import Services

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("valora")
settings = get_settings()
services: Services | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global services
    services = await run_in_threadpool(Services, settings)
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan, description="AI-powered real estate property valuation assistant over the Ames Housing dataset.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_origin_regex=r"https://.*\.vercel\.app", allow_methods=["*"], allow_headers=["*"])

# ---- minimal in-memory rate limiter (per client IP, sliding minute) ----
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "anon"
        now = time.time()
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return JSONResponse({"type": "about:blank", "title": "Too Many Requests", "status": 429, "detail": "Rate limit exceeded; retry in a minute."}, status_code=429, media_type="application/problem+json")
        q.append(now)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def problem_details(_: Request, exc: HTTPException):
    return JSONResponse({"type": "about:blank", "title": exc.detail if isinstance(exc.detail, str) else "Error", "status": exc.status_code, "detail": exc.detail}, status_code=exc.status_code, media_type="application/problem+json")


def svc() -> Services:
    if services is None:
        raise HTTPException(503, "Service is still starting")
    return services


# ---------------- endpoints ----------------

@app.get("/health", response_model=Health)
def health():
    s = svc()
    return Health(
        status="ok", version=settings.version, engine="llm" if s.llm.enabled else "rules", embedding=s.index.embedder.name, vectorStore=s.index.store.name, records=len(s.ds),
        llm=s.llm.status, latency=s.latency_stats(), uptimeS=int(time.time() - s.started_at),
    )


@app.get("/api/v1/meta")
def meta():
    s = svc()
    return {
        "neighborhoods": [{"code": c, "name": NEIGHBORHOOD_NAMES.get(c, c), **st} for c, st in sorted(s.ds.neighborhood_stats.items(), key=lambda kv: -kv[1]["median"])],
        "bounds": s.bounds, "records": len(s.ds), "model": s.pricing.metrics,
    }


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    s = svc()
    resp = await run_in_threadpool(run_pipeline, s, req.query, req.filters, req.top_k)
    s.record_latency(resp.latencyMs)
    subj = resp.classification.extractedAttributes.model_dump() if resp.classification else None
    s.feedback.log_request(resp.requestId, req.query, resp.valuation.estimate if resp.valuation else None, subj, resp.judge.verdict if resp.judge else None, resp.engine, resp.latencyMs)
    return resp


@app.post("/api/v1/search", response_model=SearchResponse)
def search(req: SearchRequest):
    s = svc()
    hits, n = s.index.search(req.query, req.filters, top_k=req.top_k, pool=max(req.top_k, settings.candidate_pool))
    return SearchResponse(query=req.query, total_candidates=n, hits=[SearchHit(property=h.property, semanticScore=round(h.semantic, 4), keywordScore=round(h.keyword, 4), hybridScore=round(h.hybrid, 4)) for h in hits])


@app.post("/api/v1/classify")
def classify_endpoint(req: SearchRequest):
    s = svc()
    c, engine = classify(s.llm, req.query, req.filters)
    return {"engine": engine, **c.model_dump()}


@app.post("/api/v1/valuation")
async def valuation(req: ValuationRequest):
    """Valuation from explicit attributes (no natural-language parsing)."""
    s = svc()
    attrs = SubjectAttributes(**req.model_dump(exclude={"top_k"}))
    if attrs.neighborhood and attrs.neighborhood not in NEIGHBORHOOD_NAMES:
        raise HTTPException(422, f"Unknown neighborhood code '{attrs.neighborhood}'")

    def _run():
        subject = Subject(attrs, s.ds, [])
        text = f"{subject.bedrooms}-bedroom home in {NEIGHBORHOOD_NAMES.get(subject.neighborhood, subject.neighborhood)} ({subject.neighborhood}), {subject.grLivArea} sq ft, built {subject.yearBuilt}, quality {subject.overallQual}, {subject.garageCars}-car garage"
        filters = QueryFilters(neighborhoods=[subject.neighborhood]) if attrs.neighborhood else QueryFilters()
        hits, _ = s.index.search(text, filters, top_k=settings.candidate_pool, pool=settings.candidate_pool)
        if len(hits) < req.top_k:
            hits, _ = s.index.search(text, QueryFilters(), top_k=settings.candidate_pool, pool=settings.candidate_pool)
        comps = prioritize(hits, subject, s.ds, req.top_k)
        pred = s.pricing.predict(subject)
        v, meta = ensemble(comps, pred, subject, s.ds)
        v.narrative, answer, _ = write_narrative(s.llm, text, subject, v, comps, pred, meta)
        jv, _ = judge(s.llm, subject, comps, v, pred, answer)
        return {"subject": subject.as_dict(), "valuation": v, "prediction": pred, "judge": jv, "comparables": comps, "answer": answer}

    return await run_in_threadpool(_run)


@app.post("/api/v1/predict", response_model=PricePrediction)
def predict(req: PredictRequest):
    s = svc()
    return s.pricing.predict(Subject(SubjectAttributes(**req.model_dump()), s.ds, []))


@app.post("/api/v1/compare", response_model=CompareResponse)
def compare(req: CompareRequest):
    s = svc()
    a, b = s.ds.by_id.get(req.a), s.ds.by_id.get(req.b)
    if not a or not b:
        raise HTTPException(404, "Unknown record id")
    im = s.impact
    base = (a.salePrice + b.salePrice) / 2
    nb_a, nb_b = im.neighborhood_premium(a.neighborhood), im.neighborhood_premium(b.neighborhood)
    factors = [
        CompareFactor(label="Neighborhood premium", amount=round(base * ((1 + nb_b) / (1 + nb_a) - 1)), why=f"{NEIGHBORHOOD_NAMES.get(b.neighborhood, b.neighborhood)} vs {NEIGHBORHOOD_NAMES.get(a.neighborhood, a.neighborhood)} hedonic fixed effect"),
        CompareFactor(label="Living area", amount=round(base * ((b.grLivArea / max(a.grLivArea, 1)) ** im.b["area"] - 1)), why=f"{b.grLivArea:,} vs {a.grLivArea:,} sq ft"),
        CompareFactor(label="Quality grade", amount=round(base * (2.718281828 ** (im.b["qual"] * (b.overallQual - a.overallQual)) - 1)), why=f"Q{b.overallQual} vs Q{a.overallQual}"),
        CompareFactor(label="Age / construction year", amount=round(base * (2.718281828 ** (im.b["year"] * (b.yearBuilt - a.yearBuilt)) - 1)), why=f"{b.yearBuilt} vs {a.yearBuilt}"),
        CompareFactor(label="Garage capacity", amount=round(base * (2.718281828 ** (im.b["garage"] * (b.garageCars - a.garageCars)) - 1)), why=f"{b.garageCars} vs {a.garageCars} cars"),
        CompareFactor(label="Basement area", amount=round(base * (2.718281828 ** (im.b["bsmt"] * (b.totalBsmtSF - a.totalBsmtSF) / 500) - 1)), why=f"{b.totalBsmtSF:,} vs {a.totalBsmtSF:,} sq ft"),
        CompareFactor(label="Condition", amount=round(base * (2.718281828 ** (im.b["cond"] * (b.overallCond - a.overallCond)) - 1)), why=f"{b.overallCond} vs {a.overallCond}"),
    ]
    diff = b.salePrice - a.salePrice
    explained = sum(f.amount for f in factors)
    factors.append(CompareFactor(label="Unexplained / market noise", amount=diff - explained, why="Timing, lot shape, sale type, interior finish and other unmodelled attributes"))
    factors.sort(key=lambda f: -abs(f.amount))
    share = min(1.0, abs(explained) / max(abs(diff), 1)) if diff else 1.0
    top = [f for f in factors if f.label != "Unexplained / market noise"][:2]
    narrative = f"{b.id} sold for ${abs(diff):,} {'more' if diff >= 0 else 'less'} than {a.id}. The hedonic model attributes most of the gap to {top[0].label.lower()} ({top[0].amount:+,}) and {top[1].label.lower()} ({top[1].amount:+,}); {share * 100:.0f}% of the difference is explained by measurable attributes."
    return CompareResponse(a=a, b=b, difference=diff, factors=factors, explainedShare=round(share, 3), narrative=narrative)


@app.post("/api/v1/properties", response_model=PropertiesResponse)
def properties(filters: QueryFilters, limit: int = 3000, offset: int = 0):
    s = svc()
    items = apply_filters(s.ds.properties, filters)
    return PropertiesResponse(items=items[offset: offset + limit], total=len(items))


@app.post("/api/v1/feedback")
def feedback(payload: FeedbackPayload):
    s = svc()
    res = s.feedback.add_feedback(payload.requestId, payload.rating, payload.correctedValue, payload.comment)
    return {"ok": True, **res, "counts": s.feedback.counts()}


@app.get("/api/v1/evaluation/latest", response_model=EvalSummary)
def evaluation_latest():
    s = svc()
    return load_latest(settings.eval_results_path, s.feedback.counts(), s.latency_stats())
