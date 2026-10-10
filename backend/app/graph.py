"""Multi-agent valuation graph, orchestrated with LangGraph.

Eight agent nodes share one typed `State`. Each node is a plain function
`state -> state`; a thin wrapper records every execution in the trace (duration,
tool, output) so the UI can show exactly what happened. Three edges are
conditional: Guardrail and Classifier can end the run early, and the Judge can
send the result back to the Retriever for one second pass with a wider
comparable pool. If a critical agent raises, every following edge routes to END
and the response says which agent failed instead of returning a partial
valuation; only the Risk Analyst is optional. The graph is synchronous and
deterministic apart from the LLM calls, which all have rule-based fallbacks."""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field, fields
from typing import Any, Callable

from langgraph.graph import END, START
from langgraph.graph import StateGraph as LGStateGraph

from app.agents.classifier import classify
from app.agents.comparables import Subject, prioritize
from app.agents.guardrails import attribute_sanity, run_guardrails
from app.agents.judge import judge
from app.agents.risk import assess_risk
from app.agents.valuer import ensemble, write_narrative
from app.retrieval.index import Hit
from app.schemas import (AgentStep, Classification, Comparable, GuardrailCheck, GuardrailResult, ImpactFactor, JudgeVerdict, PricePrediction,
                         QueryFilters, QueryResponse, RiskAssessment, Valuation)
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
    guardrails: GuardrailResult | None = None
    sanitized: str = ""
    classification: Classification | None = None
    subject: Subject | None = None
    hits: list[Hit] | None = None
    pool: int = 0
    comps: list[Comparable] | None = None
    prediction: PricePrediction | None = None
    valuation: Valuation | None = None
    meta: dict[str, Any] | None = None
    risk: RiskAssessment | None = None
    impact: list[ImpactFactor] | None = None
    judge: JudgeVerdict | None = None
    answer: str = ""
    narrative: str = ""
    blocked: bool = False
    retry: bool = False
    failed: str | None = None  # name of the critical agent that raised, if any


Node = Callable[[State], State]
_FIELDS = [f.name for f in fields(State)]
# Agents whose failure leaves the valuation intact: the run continues without their output.
OPTIONAL = {"Risk Analyst"}


def _traced(name: str, role: str, tool: str, fn: Node) -> Callable[[State], dict]:
    """Wrap an agent as a LangGraph node: run it, append an AgentStep to the trace,
    and hand the updated state back to LangGraph as a full channel update. A failing
    node is recorded as an error step; a critical one also marks the run as failed so
    the routers below stop the graph."""
    def node(state: State) -> dict:
        t0 = time.perf_counter()
        try:
            state = fn(state)
            status, output = "done", getattr(state, "trace_note", "")
        except Exception as e:  # noqa: BLE001
            log.exception("node %s failed", name)
            status, output = "error", f"{type(e).__name__}: {e}"[:160]
            if name not in OPTIONAL:
                state.failed = name
        state.trace.append(AgentStep(agent=name, role=role, status=status, durationMs=int((time.perf_counter() - t0) * 1000), output=output, tool=tool or None))
        return {k: getattr(state, k) for k in _FIELDS}
    return node


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
    s.narrative, s.answer, eng = write_narrative(s.svc.llm, s.sanitized, s.subject, s.valuation, s.comps, s.prediction, s.meta, s.classification.intent)
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
    # A rejected first pass earns one retry with a wider comparable pool.
    s.retry = s.judge.verdict == "rejected" and s.attempt == 0 and len(s.comps) > 0
    if s.retry:
        s.attempt += 1
    return _note(s, f"{s.judge.verdict} · {s.judge.score * 100:.0f}/100" + (" · requesting second pass" if s.retry else ""))


def route_after_guardrail(s: State) -> str:
    return END if s.blocked or s.failed else "Classifier"


def route_after_classify(s: State) -> str:
    return END if s.blocked or s.failed else "Retriever"


def route_after_judge(s: State) -> str:
    return "Retriever" if s.retry and not s.failed else END


def _unless_failed(target: str) -> Callable[[State], str]:
    return lambda s: END if s.failed else target


# name → (role, tool, fn); the role and tool are what the UI shows for each trace step.
AGENTS: dict[str, tuple[str, str, Node]] = {
    "Guardrail": ("Input validation", "rules + regex", n_guardrail),
    "Classifier": ("Intent & attribute extraction", "llm:structured-output", n_classify),
    "Retriever": ("Hybrid search", "bm25 + dense (RRF)", n_retrieve),
    "Comp Analyst": ("Prioritization & adjustments", "rules", n_prioritize),
    "Pricing Model": ("ML prediction", "sklearn:hgb", n_predict),
    "Valuer": ("Ensemble synthesis", "llm + rules", n_value),
    "Risk Analyst": ("Risk & impact", "stats + hedonic ols", n_risk),
    "Judge": ("Independent validation", "llm-as-judge", n_judge),
}


def build_graph():
    g = LGStateGraph(State)
    for name, (role, tool, fn) in AGENTS.items():
        g.add_node(name, _traced(name, role, tool, fn))
    g.add_edge(START, "Guardrail")
    g.add_conditional_edges("Guardrail", route_after_guardrail, ["Classifier", END])
    g.add_conditional_edges("Classifier", route_after_classify, ["Retriever", END])
    for a, b in [("Retriever", "Comp Analyst"), ("Comp Analyst", "Pricing Model"), ("Pricing Model", "Valuer"), ("Valuer", "Risk Analyst"), ("Risk Analyst", "Judge")]:
        g.add_conditional_edges(a, _unless_failed(b), [b, END])
    g.add_conditional_edges("Judge", route_after_judge, ["Retriever", END])
    return g.compile()


GRAPH = build_graph()


def run_pipeline(svc: Services, query: str, filters: QueryFilters, top_k: int = 8, exclude_ids: set[str] | None = None) -> QueryResponse:
    out = GRAPH.invoke(State(query=query, filters=filters, top_k=top_k, svc=svc, exclude_ids=exclude_ids), {"recursion_limit": 40})
    s = State(**out)
    engine = "rules" if not s.engines or all(e == "rules" for e in s.engines) else ("llm-degraded" if any(e in ("rules", "llm-degraded") for e in s.engines) else "llm")
    latency = int((time.perf_counter() - s.started) * 1000)
    if s.failed:
        step = next((t for t in reversed(s.trace) if t.agent == s.failed and t.status == "error"), None)
        log.error("pipeline %s stopped: %s failed", s.request_id, s.failed)
        guardrails = s.guardrails or GuardrailResult(passed=False, checks=[GuardrailCheck(name="Guardrail", status="fail", detail="Guardrail agent failed; request rejected (fail-closed)")])
        return QueryResponse(requestId=s.request_id, engine=engine, query=query, latencyMs=latency, guardrails=guardrails, classification=s.classification, agentTrace=s.trace,
                             answer=f"The valuation could not be completed because the {s.failed} agent failed ({step.output if step else 'unknown error'}). "
                                    "No estimate is returned rather than a partial or unvalidated one; please retry.")
    if s.blocked:
        return QueryResponse(requestId=s.request_id, engine=engine, query=query, latencyMs=latency, guardrails=s.guardrails, classification=s.classification, agentTrace=s.trace,
                             answer="The request was blocked by input guardrails before any retrieval or model call. Rephrase it as a property description or valuation question.")
    return QueryResponse(
        requestId=s.request_id, engine=engine, query=query, latencyMs=latency, guardrails=s.guardrails, classification=s.classification,
        comparables=s.comps or [], valuation=s.valuation, prediction=s.prediction, judge=s.judge, risk=s.risk, impact=s.impact or [], agentTrace=s.trace, answer=s.answer,
    )
