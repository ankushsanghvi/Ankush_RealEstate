"""Input validation guardrails. Rule-based and fast (<1 ms) so they run before
any model call; the classifier's `out_of_scope` intent is a second, semantic gate."""
from __future__ import annotations

import re
import unicodedata

from app.data.loader import NEIGHBORHOOD_NAMES
from app.schemas import GuardrailCheck, GuardrailResult

INJECTION = re.compile(
    r"(ignore (all |the )?(previous|prior|above) (instructions|prompts?)|you are now|system prompt|developer message|"
    r"disregard (your|all) (rules|instructions)|jailbreak|\bDAN\b|act as (an? )?(unrestricted|unfiltered)|reveal (your|the) (prompt|instructions))",
    re.I,
)
PII = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("phone", re.compile(r"(\+?\d[\d\s().-]{8,}\d)")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]
DOMAIN = re.compile(
    r"\b(house|home|homes|property|properties|bungalow|ranch|condo|townhouse|duplex|bed|beds|bedroom|bedrooms|bath|baths|bathroom|"
    r"sq\s?ft|sqft|square|garage|basement|lot|built|year|neighbou?rhood|comparable|comps?|valuation|value|worth|price|priced|"
    r"estimate|appraise|appraisal|sold|sale|sales|market|listing|quality|remodel|acre|story|storey|storie)\b",
    re.I,
)
OFF_TOPIC = re.compile(r"\b(stock|stocks|crypto|bitcoin|weather|recipe|joke|poem|football|movie|python code|essay)\b", re.I)


def _neighborhood_mentioned(text: str) -> bool:
    t = text.lower()
    return any(code.lower() in t or name.lower() in t for code, name in NEIGHBORHOOD_NAMES.items())


def run_guardrails(query: str, max_chars: int) -> tuple[GuardrailResult, str]:
    """Returns (result, sanitized_query)."""
    checks: list[GuardrailCheck] = []
    q = unicodedata.normalize("NFKC", query).strip()
    q = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", q)

    tokens = q.split()
    if len(q) < 8 or len(tokens) < 2:
        checks.append(GuardrailCheck(name="Length & encoding", status="fail", detail="Query too short to be actionable"))
    elif len(q) > max_chars:
        q = q[:max_chars]
        checks.append(GuardrailCheck(name="Length & encoding", status="warn", detail=f"Truncated to {max_chars} characters"))
    else:
        checks.append(GuardrailCheck(name="Length & encoding", status="pass", detail=f"{len(tokens)} tokens, NFKC-normalised"))

    if INJECTION.search(q):
        checks.append(GuardrailCheck(name="Prompt-injection scan", status="fail", detail="Instruction-override pattern detected"))
    else:
        checks.append(GuardrailCheck(name="Prompt-injection scan", status="pass", detail="No instruction-override patterns detected"))

    redacted = 0
    for label, rx in PII:
        q, n = rx.subn(f"[{label} redacted]", q)
        redacted += n
    checks.append(GuardrailCheck(name="PII redaction", status="warn" if redacted else "pass", detail=f"{redacted} identifier(s) redacted" if redacted else "No personal identifiers present"))

    on_topic = bool(DOMAIN.search(q)) or _neighborhood_mentioned(q)
    off_topic = bool(OFF_TOPIC.search(q)) and not on_topic
    if off_topic or not on_topic:
        checks.append(GuardrailCheck(name="Domain relevance", status="fail", detail="Query is outside real-estate valuation scope"))
    else:
        checks.append(GuardrailCheck(name="Domain relevance", status="pass", detail="Real-estate intent detected"))

    passed = all(c.status != "fail" for c in checks)
    return GuardrailResult(passed=passed, checks=checks), q


def attribute_sanity(attrs, bounds: dict[str, tuple[int, int]]) -> GuardrailCheck:
    """Clamp extracted attributes to the dataset's observed range (mutates attrs)."""
    clamped = []
    for field, (lo, hi) in bounds.items():
        v = getattr(attrs, field, None)
        if v is None:
            continue
        if v < lo or v > hi:
            setattr(attrs, field, min(hi, max(lo, v)))
            clamped.append(f"{field}={v}→{getattr(attrs, field)}")
    if clamped:
        return GuardrailCheck(name="Attribute sanity", status="warn", detail="Outside dataset range, clamped: " + ", ".join(clamped))
    return GuardrailCheck(name="Attribute sanity", status="pass", detail="All extracted values within dataset bounds")
