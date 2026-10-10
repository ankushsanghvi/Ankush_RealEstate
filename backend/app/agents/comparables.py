"""Comparable-property prioritization + appraisal-style adjustments.

Retrieval finds *similar text*; this agent decides what is a *comparable* in
the appraiser's sense: same neighborhood, close living area, similar age and
quality, recent sale. Scoring is deterministic and every reason is surfaced so
a reviewer can audit why a comp ranked where it did."""
from __future__ import annotations

from app.data.loader import Dataset
from app.retrieval.index import Hit
from app.schemas import Adjustment, Comparable, Property, SubjectAttributes

QUAL_STEP = 0.055        # ~5.5 % of price per quality point (from the elasticity fit)
YEAR_STEP = 0.0025       # ~0.25 % per year of age
GARAGE_STEP = 0.04       # per car bay
BSMT_PER_SF = 0.00006    # per sq ft of basement, as a fraction of price


class Subject:
    """Fully-resolved subject property (missing attributes filled from priors)."""

    def __init__(self, attrs: SubjectAttributes, ds: Dataset, anchor: list[Property]):
        pool = anchor or ds.properties
        nb = attrs.neighborhood or _mode([p.neighborhood for p in pool])
        self.neighborhood = nb
        st = ds.neighborhood_stats.get(nb, {})
        # Zero is a real answer for bedrooms (studio), garage, basement and full baths, so only
        # None falls back to a prior. Zero living area / year / quality / lot is impossible and
        # is treated as missing.
        self.bedrooms = attrs.bedrooms if attrs.bedrooms is not None else 3
        self.grLivArea = attrs.grLivArea or int(_median([p.grLivArea for p in pool]))
        self.yearBuilt = attrs.yearBuilt or int(st.get("median_year", 1975))
        self.overallQual = attrs.overallQual or int(round(st.get("median_qual", 6)))
        self.garageCars = attrs.garageCars if attrs.garageCars is not None else 2
        self.totalBsmtSF = attrs.totalBsmtSF if attrs.totalBsmtSF is not None else int(self.grLivArea * 0.7)
        self.lotArea = attrs.lotArea or 9000
        self.fullBath = attrs.fullBath if attrs.fullBath is not None else (2 if self.grLivArea > 1400 else 1)
        self.explicit = {k for k, v in attrs.model_dump().items() if v is not None}

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("neighborhood", "bedrooms", "grLivArea", "yearBuilt", "overallQual", "garageCars", "totalBsmtSF", "lotArea", "fullBath")}


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def _mode(xs):
    return max(set(xs), key=xs.count) if xs else "NAmes"


def adjustments_for(subject: Subject, p: Property) -> list[Adjustment]:
    ppsf = p.salePrice / max(p.grLivArea, 1)
    adj = [
        Adjustment(label="Living area", amount=round((subject.grLivArea - p.grLivArea) * ppsf * 0.55)),
        Adjustment(label="Quality grade", amount=round((subject.overallQual - p.overallQual) * QUAL_STEP * p.salePrice)),
        Adjustment(label="Age", amount=round((subject.yearBuilt - p.yearBuilt) * YEAR_STEP * p.salePrice)),
        Adjustment(label="Garage", amount=round((subject.garageCars - p.garageCars) * GARAGE_STEP * p.salePrice)),
        Adjustment(label="Basement", amount=round((subject.totalBsmtSF - p.totalBsmtSF) * BSMT_PER_SF * p.salePrice)),
    ]
    return [a for a in adj if a.amount != 0]


def prioritize(hits: list[Hit], subject: Subject, ds: Dataset, top_k: int) -> list[Comparable]:
    out: list[Comparable] = []
    latest_year = max(p.saleYear for p in ds.properties)
    for h in hits:
        p = h.property
        reasons: list[str] = []
        score = 0.0
        same_nb = p.neighborhood == subject.neighborhood
        if same_nb:
            score += 0.30
            reasons.append("Same neighborhood")
        d_area = abs(p.grLivArea - subject.grLivArea) / max(subject.grLivArea, 1)
        if d_area <= 0.10:
            score += 0.22
            reasons.append(f"Living area within {max(1, round(d_area * 100))}%")
        elif d_area <= 0.20:
            score += 0.12
        d_year = abs(p.yearBuilt - subject.yearBuilt)
        if d_year <= 8:
            score += 0.15
            reasons.append("Built within 8 years")
        elif d_year <= 20:
            score += 0.07
        d_q = abs(p.overallQual - subject.overallQual)
        if d_q == 0:
            score += 0.12
            reasons.append("Identical quality grade")
        elif d_q == 1:
            score += 0.07
        if p.bedroomAbvGr == subject.bedrooms:
            score += 0.06
            reasons.append("Same bedroom count")
        if p.garageCars == subject.garageCars:
            score += 0.03
        if p.saleYear >= latest_year - 1:
            score += 0.04
            reasons.append("Recent sale")
        priority = min(1.0, 0.15 * h.hybrid + 0.85 * score)
        adj = adjustments_for(subject, p)
        out.append(Comparable(
            property=p, semanticScore=round(h.semantic, 4), keywordScore=round(h.keyword, 4), hybridScore=round(h.hybrid, 4),
            priorityScore=round(priority, 4), priorityReasons=reasons, adjustments=adj, adjustedPrice=p.salePrice + sum(a.amount for a in adj),
        ))
    out.sort(key=lambda c: -c.priorityScore)
    return out[:top_k]
