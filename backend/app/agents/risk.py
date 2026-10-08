"""Property value-risk prediction. A valuation is risky when the evidence is
thin (few in-neighborhood comps), noisy (adjusted comps disagree), the
neighborhood itself is volatile, or the two estimation methods diverge."""
from __future__ import annotations

import numpy as np

from app.data.loader import Dataset
from app.schemas import Comparable, RiskAssessment, RiskDriver


def assess_risk(comps: list[Comparable], subject, ds: Dataset, comp_estimate: float, ml_estimate: float) -> RiskAssessment:
    st = ds.neighborhood_stats.get(subject.neighborhood, {"count": 0, "ppsf_cv": 0.25})
    prices = np.array([c.adjustedPrice for c in comps], dtype=float)
    dispersion = float(prices.std() / prices.mean()) if len(prices) > 1 else 0.3
    same_nb = sum(1 for c in comps if c.property.neighborhood == subject.neighborhood)
    divergence = abs(ml_estimate - comp_estimate) / max(comp_estimate, 1)
    age = max(0, 2010 - subject.yearBuilt)
    vol = float(st.get("ppsf_cv", 0.25))

    drivers = [
        RiskDriver(label="Comparable dispersion", weight=int(round(min(40, dispersion * 150))), direction="up"),
        RiskDriver(label="Neighborhood coverage", weight=int(8 if same_nb >= 3 else 22 if same_nb >= 1 else 32), direction="down" if same_nb >= 3 else "up"),
        RiskDriver(label="Method divergence", weight=int(round(min(30, divergence * 150))), direction="up" if divergence > 0.05 else "down"),
        RiskDriver(label="Neighborhood volatility", weight=int(round(min(25, vol * 80))), direction="up" if vol > 0.2 else "down"),
        RiskDriver(label="Property age", weight=int(min(20, age // 5)), direction="up" if age > 40 else "down"),
        RiskDriver(label="Quality grade", weight=int(10 if subject.overallQual >= 7 else 4), direction="down" if subject.overallQual >= 7 else "up"),
    ]
    score = 10
    for d in drivers:
        score += d.weight if d.direction == "up" else -d.weight * 0.35
    score = int(np.clip(round(score), 3, 97))
    level = "low" if score < 30 else "moderate" if score < 50 else "elevated" if score < 70 else "high"
    return RiskAssessment(level=level, score=score, drivers=drivers, volatility12m=round(vol, 4), neighborhoodSales=int(st.get("count", 0)))
