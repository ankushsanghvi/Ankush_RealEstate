"""Property classification agent: intent + property type + structured attribute
extraction. LLM (structured output) when available, regex/lexicon otherwise.
The regex extractor always runs and back-fills anything the LLM left null, so
numbers typed explicitly by the user are never lost."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.llm import LLM
from app.data.loader import NEIGHBORHOOD_NAMES
from app.schemas import Classification, QueryFilters, SubjectAttributes

QUAL_WORDS = {"excellent": 9, "very good": 8, "good": 7, "above average": 6, "average": 5, "below average": 4, "fair": 3, "poor": 2}


class LLMClassification(BaseModel):
    intent: Literal["similar_properties", "valuation", "comparison", "price_difference", "market_insight", "out_of_scope"]
    propertyType: Literal["single_family", "townhouse", "duplex", "unknown"]
    confidence: float = Field(ge=0, le=1)
    neighborhood: str | None = Field(default=None, description="Ames neighborhood code, e.g. CollgCr, NAmes, NridgHt")
    bedrooms: int | None = None
    grLivArea: int | None = Field(default=None, description="Above-grade living area in sq ft")
    yearBuilt: int | None = None
    overallQual: int | None = Field(default=None, description="1-10 overall quality")
    garageCars: int | None = None
    totalBsmtSF: int | None = None
    lotArea: int | None = None
    fullBath: int | None = None
    rationale: str = Field(description="One sentence, max 30 words")


SYSTEM = (
    "You are the classification agent of a real-estate valuation assistant for Ames, Iowa. "
    "Classify the user's intent and extract any property attributes that are explicitly stated. "
    "Never invent attributes that are not in the query. Neighborhood must be one of these codes: "
    + ", ".join(f"{c} ({n})" for c, n in NEIGHBORHOOD_NAMES.items())
    + ". Quality words map to 1-10 (poor=2, fair=3, average=5, good=7, very good=8, excellent=9)."
)


def extract_regex(query: str) -> SubjectAttributes:
    q = query.lower().replace(",", "")
    attrs = SubjectAttributes()
    # The subject is the first neighborhood mentioned ("Northridge Heights vs Old Town" → NridgHt);
    # at the same position the longer name wins, so "Northridge Heights" beats "Northridge".
    mentions = []
    for code, name in NEIGHBORHOOD_NAMES.items():
        for term in (name.lower(), code.lower()):
            if m := re.search(rf"\b{re.escape(term)}\b", q):
                mentions.append((m.start(), -len(term), code))
    if mentions:
        attrs.neighborhood = min(mentions)[2]
    if m := re.search(r"\b(\d{1,2})\s*-?\s*(bed|br\b|bedroom|bd\b)", q):
        attrs.bedrooms = int(m.group(1))
    if m := re.search(r"(?<![\d.])(\d{1,2})(?:\.5)?\s*-?\s*(bath|ba\b)", q):
        attrs.fullBath = int(m.group(1))
    if m := re.search(r"(\d{3,5})\s*(sq\s?ft|sqft|square feet|sf\b)", q):
        attrs.grLivArea = int(m.group(1))
    if m := re.search(r"(?:built|from|circa|in)\s*(?:around|about|~)?\s*((?:18|19|20)\d{2})\b(?!\s*(?:sq|sf|square))", q):
        attrs.yearBuilt = int(m.group(1))
    elif m := re.search(r"\b((?:19|20)\d0)s\b", q):
        attrs.yearBuilt = int(m.group(1)) + 5
    if m := re.search(r"quality\s*(?:of|grade|is|=|:)?\s*(\d{1,2})", q) or re.search(r"\bq(\d{1,2})\b", q):
        attrs.overallQual = int(m.group(1))
    else:
        for word, val in QUAL_WORDS.items():
            if re.search(rf"\b{word}\b\s*(quality|condition|grade)?", q) and re.search(rf"\b{word}\b", q):
                attrs.overallQual = val
                break
    if m := re.search(r"\b(\d{1,2})\s*-?\s*car", q):
        attrs.garageCars = int(m.group(1))
    elif re.search(r"\bno garage\b", q):
        attrs.garageCars = 0
    if m := re.search(r"(\d{3,5})\s*(sq\s?ft|sqft)?\s*(finished\s*)?basement", q):
        attrs.totalBsmtSF = int(m.group(1))
    elif re.search(r"\bno basement\b", q):
        attrs.totalBsmtSF = 0
    if m := re.search(r"(\d{4,6})\s*(sq\s?ft|sqft)\s*lot", q) or re.search(r"lot\s*(?:of|is)?\s*(\d{4,6})", q):
        attrs.lotArea = int(m.group(1))
    if m := re.search(r"(\d+(?:\.\d+)?)\s*acres?", q):
        attrs.lotArea = int(float(m.group(1)) * 43560)
    return attrs


def intent_regex(query: str) -> str:
    q = query.lower()
    if re.search(r"\b(why|explain|differ|difference|more than|less than|versus|vs\.?)\b", q) and re.search(r"\b(than|vs|versus|differ|difference|why)\b", q):
        return "price_difference"
    if re.search(r"\b(compare|comparison|side by side)\b", q):
        return "comparison"
    if re.search(r"\b(worth|value|valuation|estimate|appraise|appraisal|price|how much)\b", q):
        return "valuation"
    if re.search(r"\b(trend|market|median|average price|premium|neighbou?rhood analysis)\b", q):
        return "market_insight"
    return "similar_properties"


def property_type_regex(query: str) -> str:
    q = query.lower()
    if re.search(r"\b(townhouse|townhome|town house)\b", q):
        return "townhouse"
    if re.search(r"\b(duplex|two-family|two family)\b", q):
        return "duplex"
    if re.search(r"\b(house|home|bungalow|ranch|single-family|single family|colonial|split)\b", q):
        return "single_family"
    return "unknown"


def classify(llm: LLM, query: str, filters: QueryFilters) -> tuple[Classification, str]:
    regex_attrs = extract_regex(query)
    engine = "rules"
    base: Classification
    out, engine = llm.parse(SYSTEM, f"Query: {query}", LLMClassification, max_tokens=400, tier="fast")
    if out is not None:
        attrs = SubjectAttributes(**{k: getattr(out, k) for k in SubjectAttributes.model_fields})
        if attrs.neighborhood and attrs.neighborhood not in NEIGHBORHOOD_NAMES:
            attrs.neighborhood = None
        base = Classification(intent=out.intent, confidence=out.confidence, propertyType=out.propertyType, extractedAttributes=attrs, rationale=out.rationale)
    else:
        attrs = SubjectAttributes()
        intent = intent_regex(query)
        found = [k for k, v in regex_attrs.model_dump().items() if v is not None]
        base = Classification(
            intent=intent, confidence=0.72 + 0.04 * min(len(found), 5), propertyType=property_type_regex(query), extractedAttributes=attrs,
            rationale=f"Rule-based classification: intent '{intent}' from query verbs; extracted {', '.join(found) if found else 'no explicit attributes'} via pattern matching.",
        )
    # Back-fill from regex, then from explicit filters (filters are user-stated facts).
    merged = base.extractedAttributes
    for k, v in regex_attrs.model_dump().items():
        if getattr(merged, k) is None and v is not None:
            setattr(merged, k, v)
    if merged.neighborhood is None and filters.neighborhoods and len(filters.neighborhoods) == 1:
        merged.neighborhood = filters.neighborhoods[0]
    if merged.bedrooms is None and filters.minBedrooms is not None and filters.minBedrooms == filters.maxBedrooms:
        merged.bedrooms = filters.minBedrooms
    base.extractedAttributes = merged
    return base, engine
