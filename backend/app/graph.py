"""Multi-agent valuation graph.

A small, explicit state machine (no framework): each node is a function
`state -> state`, edges are declared, one edge is conditional (the judge can
send the result back for a second pass with a wider comparable pool). Every
node execution is recorded in the trace with duration, tool and output so the
UI can show exactly what happened. The whole graph is synchronous and
deterministic apart from the LLM calls, which all have rule-based fallbacks."""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from app.agents.classifier import classify
from app.agents.comparables import Subject, prioritize
from app.agents.guardrails import attribute_sanity, run_guardrails
from app.agents.judge import judge
from app.agents.risk import assess_risk
from app.agents.valuer import ensemble, write_narrative
from app.schemas import AgentStep, GuardrailCheck, QueryFilters, QueryResponse
from app.services import Services

log = logging.getLogger(__name__)


@dataclass
class State:
    query: str
    filters: QueryFilters
    top_k: int
    svc: Services
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:10]}")
    started: float = field(default_factory=time.perf_counter)
    engines: list[str] = field(default_factory=list)
    trace: list[AgentStep] = field(default_factory=list)
    attempt: int = 0
    exclude_ids: set[str] | None = None
    # populated along the way
    guardrails=None; sanitized: str = ""; classification=None; subject=None; hits=None; pool: int = 0
    comps=None; prediction=None; valuation=None; meta=None; risk=None; impact=None; judge=None; answer: str = ""; narrative: str = ""
    blocked: bool = False


Node = Callable[[State], State]


class StateGraph:
    def __init__(self):
        self.nodes: dict[str, tuple[str, str, Node]] = {}
        self.edges: dict[str, str | Callable[[State], str]] = {}
        self.entry: str | None = None

    def add(self, name: str, role: str, fn: Node, tool: str = ""):
        self.nodes[name] = (role, tool, fn)
        if self.entry is None:
            self.entry = name
        return self

    def edge(self, src: str, dst: str | Callable[[State], str]):
        self.edges[src] = dst
        return self

    def run(self, state: State) -> State:
        cur = self.entry
        guard = 0
        while cur and cur != "END" and guard < 40:
            guard += 1
            role, tool, fn = self.nodes[cur]
            t0 = time.perf_counter()
            try:
                out = fn(state)
                state = out
                status = "done"
                output = state.trace_note if hasattr(state, "trace_note") else ""
            except Exception as e:  # noqa: BLE001
                log.exception("node %s failed", cur)
                status = "error"
                output = f"{type(e).__name__}: {e}"[:160]
            state.trace.append(AgentStep(agent=cur, role=role, status=status, durationMs=int((time.perf_counter() - t0) * 1000), output=output, tool=tool or None))
            nxt = self.edges.get(cur, "END")
            cur = nxt(state) if callable(nxt) else nxt
        return state


def _note(state: State, text: str) -> State:
    state.trace_note = text  # type: ignore[attr-defined]
    return state


# ---------------- nodes ----------------

def n_guardrail(s: State) -> State:
    s.guardrails, s.sanitized = run_guardrails(s.query, s.svc.settings.max_query_chars)
    s.blocked = not s.guardrails.passed
    fails = [c.name for c in s.guardrails.checks if c.status == "fail"]
    return _note(s, f"{len(s.guardrails.checks)} checks · " + ("blocked: " + ", ".join(fails) if fails else "intent in scope"))


def n_classify(s: State) -> State:
    s.classification, eng = classify(s.svc.llm, s.sanitized, s.filters)
    s.engines.append(eng)
    attrs = s.classification.extractedAttributes
    s.guardrails.checks.append(attribute_sanity(attrs, s.svc.bounds))
    if s.classification.intent == "out_of_scope":
        s.blocked = True
        s.guardrails.passed = False
        s.guardrails.checks.append(GuardrailCheck(name="Semantic scope", status="fail", detail="Classifier judged the query out of scope"))
    found = {k: v for k, v in attrs.model_dump().items() if v is not None}
    return _note(s, f"intent={s.classification.intent} · {found or 'no explicit attributes'}")


def n_retrieve(s: State) -> State:
    pool = s.svc.settings.candidate_pool * (1 + s.attempt)
    s.hits, s.pool = s.svc.index.search(s.sanitized, s.filters, top_k=pool, pool=pool, exclude_ids=s.exclude_ids)
    anchored = 0
    nb = s.classification.extractedAttributes.neighborhood
    # Neighborhood anchoring: if the query names a neighborhood but the text search
    # drifted (e.g. "Somerset vs Gilbert"), add a pass constrained to that neighborhood
    # so the comparable set is drawn from where the subject actually is.
    if nb and not s.filters.neighborhoods and sum(1 for h in s.hits if h.property.neighborhood == nb) < s.top_k:
        extra, _ = s.svc.index.search(s.sanitized, s.filters.model_copy(update={"neighborhoods": [nb]}), top_k=pool, pool=pool, exclude_ids=s.exclude_ids)
        seen = {h.property.id for h in s.hits}
        new = [h for h in extra if h.property.id not in seen]
        anchored = len(new)
        s.hits = s.hits + new
    s.subject = Subject(s.classification.extractedAttributes, s.svc.ds, [h.property for h in s.hits[:10]])
    return _note(s, f"BM25 ∪ dense → {len(s.hits)} candidates · RRF fused · metadata filter kept {s.pool}/{len(s.svc.ds)}" + (f" · +{anchored} anchored to {nb}" if anchored else ""))


def n_prioritize(s: State) -> State:
    s.comps = prioritize(s.hits, s.subject, s.svc.ds, s.top_k)
    same = sum(1 for c in s.comps if c.property.neighborhood == s.subject.neighborhood)
    return _note(s, f"Top {len(s.comps)} comparables ({same} in {s.subject.neighborhood}) · adjustments computed")


def n_predict(s: State) -> State:
    s.prediction = s.svc.pricing.predict(s.subject)
    return _note(s, f"${s.prediction.prediction:,} (90% ${s.prediction.low:,}–${s.prediction.high:,})")


def n_value(s: State) -> State:
    s.valuation, s.meta = ensemble(s.comps, s.prediction, s.subject, s.svc.ds)
    s.narrative, s.answer, eng = write_narrative(s.svc.llm, s.sanitized, s.subject, s.valuation, s.comps, s.prediction, s.meta)
    s.valuation.narrative = s.narrative
    s.engines.append(eng)
    return _note(s, f"${s.valuation.estimate:,} · conf {s.valuation.confidence * 100:.0f}% · comps weight {s.meta['w_comp'] * 100:.0f}%")


def n_risk(s: State) -> State:
    s.risk = assess_risk(s.comps, s.subject, s.svc.ds, s.meta["comp_estimate"] or s.prediction.prediction, s.prediction.prediction)
    s.impact = s.svc.impact.factors(s.subject)
    return _note(s, f"{s.risk.level} risk · score {s.risk.score} · {s.risk.neighborhoodSales} sales in neighborhood")


def n_judge(s: State) -> State:
    s.judge, eng = judge(s.svc.llm, s.subject, s.comps, s.valuation, s.prediction, s.answer)
    s.engines.append(eng)
    return _note(s, f"{s.judge.verdict} · {s.judge.score * 100:.0f}/100" + (" · requesting second pass" if s.judge.verdict == "rejected" and s.attempt == 0 else ""))


def route_after_guardrail(s: State) -> str:
    return "END" if s.blocked else "Classifier"


def route_after_classify(s: State) -> str:
    return "END" if s.blocked else "Retriever"


def route_after_judge(s: State) -> str:
    if s.judge.verdict == "rejected" and s.attempt == 0 and len(s.comps) > 0:
        s.attempt += 1
        return "Retriever"
    return "END"


def build_graph() -> StateGraph:
    g = StateGraph()
    g.add("Guardrail", "Input validation", n_guardrail, "rules + regex")
    g.add("Classifier", "Intent & attribute extraction", n_classify, "llm:structured-output")
    g.add("Retriever", "Hybrid search", n_retrieve, "bm25 + dense (RRF)")
    g.add("Comp Analyst", "Prioritization & adjustments", n_prioritize, "rules")
    g.add("Pricing Model", "ML prediction", n_predict, "sklearn:hgb")
    g.add("Valuer", "Ensemble synthesis", n_value, "llm + rules")
    g.add("Risk Analyst", "Risk & impact", n_risk, "stats + hedonic ols")
    g.add("Judge", "Independent validation", n_judge, "llm-as-judge")
    g.edge("Guardrail", route_after_guardrail).edge("Classifier", route_after_classify).edge("Retriever", "Comp Analyst")
    g.edge("Comp Analyst", "Pricing Model").edge("Pricing Model", "Valuer").edge("Valuer", "Risk Analyst").edge("Risk Analyst", "Judge").edge("Judge", route_after_judge)
    return g


GRAPH = build_graph()


def run_pipeline(svc: Services, query: str, filters: QueryFilters, top_k: int = 8, exclude_ids: set[str] | None = None) -> QueryResponse:
    s = GRAPH.run(State(query=query, filters=filters, top_k=top_k, svc=svc, exclude_ids=exclude_ids))
    engine = "rules" if not s.engines or all(e == "rules" for e in s.engines) else ("llm-degraded" if any(e in ("rules", "llm-degraded") for e in s.engines) else "llm")
    latency = int((time.perf_counter() - s.started) * 1000)
    if s.blocked:
        return QueryResponse(requestId=s.request_id, engine=engine, query=query, latencyMs=latency, guardrails=s.guardrails, classification=s.classification, agentTrace=s.trace,
                             answer="The request was blocked by input guardrails before any retrieval or model call. Rephrase it as a property description or valuation question.")
    return QueryResponse(
        requestId=s.request_id, engine=engine, query=query, latencyMs=latency, guardrails=s.guardrails, classification=s.classification,
        comparables=s.comps, valuation=s.valuation, prediction=s.prediction, judge=s.judge, risk=s.risk, impact=s.impact, agentTrace=s.trace, answer=s.answer,
    )
