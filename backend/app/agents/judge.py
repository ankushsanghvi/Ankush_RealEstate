"""LLM-as-judge for valuation validation.

Five criteria, each with a deterministic check. The LLM judge is *independent*
(separate prompt, sees only evidence) and may fail a criterion the rules passed,
but it can never pass one the numbers failed, and its verdict is never more
favourable than the deterministic one. Without an LLM the checks stand alone."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.llm import LLM
from app.agents.valuer import comp_weighted
from app.schemas import Comparable, JudgeCriterion, JudgeVerdict, PricePrediction, Valuation


class LLMCriterion(BaseModel):
    name: str
    passed: bool
    note: str = Field(description="One sentence, max 25 words, citing a number")


class LLMJudge(BaseModel):
    criteria: list[LLMCriterion] = Field(min_length=5, max_length=5)
    summary: str = Field(description="Max 40 words")
    score: float = Field(ge=0, le=1)


SYSTEM = (
    "You are an independent valuation reviewer. You did not produce this valuation. Evaluate it strictly against the evidence provided. "
    "Return exactly five criteria with these names in order: 'Comparable relevance', 'Model agreement', 'Adjustment reasonableness', "
    "'Grounded narrative', 'Range calibration'. For each, decide pass/fail and give a one-sentence note citing numbers. "
    "The deterministic pre-checks are given; override one only if you can state why. Score 0-1 overall."
)


def _numbers(text: str) -> set[int]:
    nums = {int(n.replace(",", "")) for n in re.findall(r"\$?(\d{1,3}(?:,\d{3})+|\d{4,7})", text)}
    # Shorthand such as "$185k" or "$1.2M" must be checked too, or it slips past grounding.
    nums |= {int(float(n) * (1_000 if u.lower() == "k" else 1_000_000)) for n, u in re.findall(r"\$(\d+(?:\.\d+)?)\s*([kKmM])\b", text)}
    return nums


def deterministic_checks(subject, comps: list[Comparable], v: Valuation, pred: PricePrediction, answer: str) -> list[JudgeCriterion]:
    same_nb = sum(1 for c in comps if c.property.neighborhood == subject.neighborhood)
    div = abs(pred.prediction - v.estimate) / max(v.estimate, 1)
    adj_ok = all(abs(sum(a.amount for a in c.adjustments)) <= 0.3 * c.property.salePrice for c in comps) if comps else False
    width = (v.high - v.low) / max(v.estimate, 1)
    comp_est, spread = comp_weighted(comps)  # the valuer is shown both figures and may cite them
    known = {v.estimate, v.low, v.high, pred.prediction, pred.low, pred.high, v.pricePerSqft, subject.grLivArea, subject.yearBuilt, subject.lotArea, subject.totalBsmtSF,
             int(round(comp_est / 500) * 500), int(spread)}
    for c in comps:
        known |= {c.property.salePrice, c.adjustedPrice, c.property.grLivArea, c.property.yearBuilt, c.property.saleYear, c.property.lotArea, c.property.totalBsmtSF, c.property.yearRemodAdd}
        known |= {abs(a.amount) for a in c.adjustments}
    mentioned = {n for n in _numbers(answer) if n >= 1000}
    ungrounded = {n for n in mentioned if not any(abs(n - k) <= max(500, 0.01 * k) for k in known)}
    return [
        JudgeCriterion(name="Comparable relevance", pass_=same_nb >= 2 and len(comps) >= 3, note=f"{same_nb}/{len(comps)} comparables share the subject neighborhood"),
        JudgeCriterion(name="Model agreement", pass_=div < 0.10, note=f"Ensemble vs. ML estimate differ by {div * 100:.1f}%"),
        JudgeCriterion(name="Adjustment reasonableness", pass_=adj_ok, note="Net adjustments within ±30% of sale price on all comps" if adj_ok else "At least one comp needs >30% net adjustment"),
        JudgeCriterion(name="Grounded narrative", pass_=not ungrounded, note="Every figure in the narrative traces to a retrieved record or computed value" if not ungrounded else f"Unsupported figures: {sorted(ungrounded)[:3]}"),
        JudgeCriterion(name="Range calibration", pass_=0.05 <= width <= 0.35, note=f"Interval width {width * 100:.0f}% of estimate"),
    ]


def score_from(criteria: list[JudgeCriterion]) -> float:
    weights = [0.3, 0.2, 0.15, 0.2, 0.15]
    return round(sum(w for w, c in zip(weights, criteria) if c.pass_), 3)


def verdict_from(score: float, criteria: list[JudgeCriterion]) -> Literal["approved", "flagged", "rejected"]:
    grounded = criteria[3].pass_
    if not grounded or score < 0.5:
        return "rejected"
    return "approved" if score >= 0.8 else "flagged"


def judge(llm: LLM, subject, comps: list[Comparable], v: Valuation, pred: PricePrediction, answer: str) -> tuple[JudgeVerdict, str]:
    checks = deterministic_checks(subject, comps, v, pred, answer)
    base_score = score_from(checks)
    base_verdict = verdict_from(base_score, checks)
    summaries = {
        "approved": "Valuation is well-supported by in-neighborhood comparables and corroborated by the ML model.",
        "flagged": "Valuation is plausible but at least one check is weak; review the comparable set before publishing.",
        "rejected": "Insufficient or ungrounded evidence; this valuation should not be relied upon without manual review.",
    }
    if not llm.enabled:
        return JudgeVerdict(verdict=base_verdict, score=base_score, criteria=checks, summary=summaries[base_verdict]), "rules"

    user = (
        f"Subject: {subject.as_dict()}\nValuation: estimate ${v.estimate:,}, range ${v.low:,}–${v.high:,}, confidence {v.confidence:.2f}\n"
        f"ML prediction: ${pred.prediction:,} (interval ${pred.low:,}–${pred.high:,}, CV MAPE {pred.mape:.3f})\n"
        f"Narrative under review: {answer}\n\nComparables:\n"
        + "\n".join(f"- {c.property.id} {c.property.neighborhood} sold ${c.property.salePrice:,} adj ${c.adjustedPrice:,} net {sum(a.amount for a in c.adjustments):+,} reasons {c.priorityReasons}" for c in comps)
        + "\n\nDeterministic pre-checks:\n" + "\n".join(f"- {c.name}: {'PASS' if c.pass_ else 'FAIL'} — {c.note}" for c in checks)
    )
    out, engine = llm.parse(SYSTEM, user, LLMJudge, max_tokens=700)
    if out is None:
        return JudgeVerdict(verdict=base_verdict, score=base_score, criteria=checks, summary=summaries[base_verdict]), "rules"
    # One-directional override: a deterministic FAIL stands (with its numeric note); the LLM
    # may only turn a PASS into a FAIL. Mismatched criterion names keep the deterministic check.
    criteria = [
        JudgeCriterion(name=d.name, pass_=c.passed, note=c.note or d.note) if d.pass_ and c.name.lower() == d.name.lower() else d
        for c, d in zip(out.criteria, checks)
    ]
    # The LLM's holistic score can lower the rule score but never raise it, so the verdict is
    # never more favourable than the deterministic one.
    rule_score = score_from(criteria)
    score = round(min(0.5 * out.score + 0.5 * rule_score, rule_score), 3)
    return JudgeVerdict(verdict=verdict_from(score, criteria), score=score, criteria=criteria, summary=out.summary), engine
