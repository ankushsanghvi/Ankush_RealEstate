"""Valuer: reconciles the comparable-weighted estimate with the ML prediction
into one recommendation with a calibrated range, then writes the narrative.
The LLM only *phrases* numbers the code computed; it never produces them."""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from app.agents.llm import LLM
from app.data.loader import Dataset, NEIGHBORHOOD_NAMES
from app.schemas import Comparable, PricePrediction, Valuation


class Narrative(BaseModel):
    narrative: str = Field(description="2 sentences (max 60 words) explaining how the estimate was derived, citing comparable ids")
    answer: str = Field(description="A direct 3-sentence answer (max 90 words) to the user's question, citing the estimate, range and the strongest comparable")


SYSTEM = (
    "You are the valuer agent of a real-estate assistant. Write for a professional appraiser. "
    "Use ONLY the numbers and record ids given to you; do not invent facts, comparables, or figures. "
    "Format dollar amounts with commas. Be concise and specific."
)


def comp_weighted(comps: list[Comparable]) -> tuple[float, float]:
    if not comps:
        return 0.0, 0.0
    w = np.array([c.priorityScore ** 2 for c in comps])
    p = np.array([c.adjustedPrice for c in comps], dtype=float)
    est = float((w * p).sum() / w.sum())
    spread = float(np.sqrt(((p - est) ** 2 * w).sum() / w.sum()))
    return est, spread


def ensemble(comps: list[Comparable], pred: PricePrediction, subject, ds: Dataset) -> tuple[Valuation, dict]:
    comp_est, spread = comp_weighted(comps)
    same_nb = sum(1 for c in comps if c.property.neighborhood == subject.neighborhood)
    n = len(comps)
    # More weight on comps when the evidence is good (many in-neighborhood comps, low spread).
    w_comp = 0.35 + 0.1 * min(same_nb, 4) - min(0.2, (spread / max(comp_est, 1)) * 0.8)
    w_comp = float(np.clip(w_comp, 0.25, 0.75)) if n else 0.0
    est = w_comp * comp_est + (1 - w_comp) * pred.prediction if n else float(pred.prediction)
    ml_half = (pred.high - pred.low) / 2
    half = w_comp * spread * 1.1 + (1 - w_comp) * ml_half if n else ml_half
    half = max(half, est * 0.035)
    divergence = abs(pred.prediction - comp_est) / max(est, 1) if n else 0.0
    confidence = float(np.clip(0.97 - (half / est) * 1.6 - divergence * 0.8 - (0.05 if same_nb < 2 else 0) - (0.08 if n < 4 else 0), 0.3, 0.95))
    r = lambda x: int(round(x / 500) * 500)
    v = Valuation(
        estimate=r(est), low=r(est - half), high=r(est + half), confidence=round(confidence, 3),
        method="ensemble" if n else "ml_model", pricePerSqft=int(round(est / max(subject.grLivArea, 1))), narrative="",
    )
    meta = {"comp_estimate": comp_est, "spread": spread, "w_comp": w_comp, "same_nb": same_nb, "divergence": divergence}
    return v, meta


def write_narrative(llm: LLM, query: str, subject, v: Valuation, comps: list[Comparable], pred: PricePrediction, meta: dict) -> tuple[str, str, str]:
    name = NEIGHBORHOOD_NAMES.get(subject.neighborhood, subject.neighborhood)
    top = comps[0] if comps else None
    comp_est = int(round(meta["comp_estimate"] / 500) * 500)
    fallback_narr = (
        f"Weighted {len(comps)} prioritized comparables ({meta['same_nb']} in {name}) after adjustments for living area, quality, age, garage and basement "
        f"(comparable-weighted figure ${comp_est:,}). The gradient-boosted model independently predicts ${pred.prediction:,}; the ensemble gives "
        f"{meta['w_comp'] * 100:.0f}% weight to comparables because {'neighborhood coverage is strong' if meta['same_nb'] >= 3 else 'in-neighborhood evidence is limited'}."
    ) if comps else f"No comparable sales matched the filters, so the estimate relies on the ML model alone (${pred.prediction:,})."
    fallback_answer = (
        f"Based on {len(comps)} prioritized comparable sales, a {subject.bedrooms}-bedroom home of {subject.grLivArea:,} sq ft in {name} built around {subject.yearBuilt} "
        f"with quality grade {subject.overallQual} is estimated at ${v.estimate:,} (range ${v.low:,} – ${v.high:,}, ${v.pricePerSqft}/sq ft)."
        + (f" The strongest comparable is {top.property.id}, which sold for ${top.property.salePrice:,} in {top.property.saleYear} and adjusts to ${top.adjustedPrice:,}." if top else "")
        + (" The comparable-weighted and model estimates agree closely." if meta["divergence"] < 0.05 else f" The two methods differ by {meta['divergence'] * 100:.0f}%, so the range is widened accordingly.")
    )
    if not llm.enabled:
        return fallback_narr, fallback_answer, "rules"
    comp_lines = "\n".join(
        f"- {c.property.id}: {NEIGHBORHOOD_NAMES.get(c.property.neighborhood, c.property.neighborhood)}, {c.property.bedroomAbvGr}bd, {c.property.grLivArea} sqft, built {c.property.yearBuilt}, Q{c.property.overallQual}, sold ${c.property.salePrice:,} ({c.property.saleYear}), adjusted ${c.adjustedPrice:,}, priority {c.priorityScore:.2f}, reasons: {', '.join(c.priorityReasons) or 'none'}"
        for c in comps
    )
    user = (
        f"User question: {query}\n\nSubject: {subject.as_dict()}\n"
        f"Comparable-weighted estimate: ${comp_est:,} (spread ${int(meta['spread']):,}); ML prediction: ${pred.prediction:,} (90% interval ${pred.low:,}–${pred.high:,}).\n"
        f"Final ensemble: estimate ${v.estimate:,}, range ${v.low:,}–${v.high:,}, confidence {v.confidence * 100:.0f}%, comparables weight {meta['w_comp'] * 100:.0f}%.\n"
        f"Comparables:\n{comp_lines}"
    )
    out, engine = llm.parse(SYSTEM, user, Narrative, max_tokens=500)
    if out is None:
        return fallback_narr, fallback_answer, "rules"
    return out.narrative, out.answer, engine
