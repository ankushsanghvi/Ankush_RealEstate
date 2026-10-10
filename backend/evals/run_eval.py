"""Built-in evaluation runner (no API key required).

Computes retrieval, valuation, grounding, judge-agreement and guardrail
metrics over evals/golden_set.json plus any human-corrected cases from the
feedback database, and writes evals/results/latest.json in the shape the
/api/v1/evaluation/latest endpoint and the UI expect. DeepEval (run_deepeval.py)
produces the same file from LLM-graded metrics when a key is available."""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402
from app.data.loader import NEIGHBORHOOD_NAMES  # noqa: E402
from app.graph import run_pipeline  # noqa: E402
from app.schemas import QueryFilters  # noqa: E402
from app.services import Services  # noqa: E402

ROOT = Path(__file__).parent
THRESHOLDS = {"Faithfulness": 0.85, "Answer relevancy": 0.80, "Contextual precision": 0.70, "Contextual recall": 0.70, "Hallucination": 0.10, "Valuation MAPE": 0.15, "Intent accuracy": 0.85, "Guardrail accuracy": 0.95, "Range coverage": 0.70}
LOWER_IS_BETTER = {"Hallucination", "Valuation MAPE"}


def numbers(text: str) -> set[int]:
    return {int(n.replace(",", "")) for n in re.findall(r"\$?(\d{1,3}(?:,\d{3})+|\d{4,7})", text)}


def grounded_share(resp) -> float:
    known = set()
    if resp.valuation:
        known |= {resp.valuation.estimate, resp.valuation.low, resp.valuation.high, resp.valuation.pricePerSqft}
    if resp.prediction:
        known |= {resp.prediction.prediction, resp.prediction.low, resp.prediction.high}
    if resp.classification:
        known |= {v for v in resp.classification.extractedAttributes.model_dump().values() if isinstance(v, int)}
    for c in resp.comparables:
        p = c.property
        known |= {p.salePrice, c.adjustedPrice, p.grLivArea, p.yearBuilt, p.saleYear, p.lotArea, p.totalBsmtSF, p.yearRemodAdd}
        known |= {abs(a.amount) for a in c.adjustments}
    mentioned = {n for n in numbers(resp.answer) if n >= 1000}
    if not mentioned:
        return 1.0
    ok = sum(1 for n in mentioned if any(abs(n - k) <= max(500, 0.01 * k) for k in known))
    return ok / len(mentioned)


def run(write: bool = True, limit: int | None = None) -> dict:
    svc = Services(get_settings())
    gs = json.loads((ROOT / "golden_set.json").read_text())
    cases = gs["cases"]
    if limit:  # stratified subset: keep every kind represented (used for the slower LLM-mode run)
        by_kind: dict[str, list] = {}
        for c in cases:
            by_kind.setdefault(c["kind"], []).append(c)
        share = {"valuation": 0.6, "retrieval": 0.25, "guardrail": 0.15}
        cases = [c for k, xs in by_kind.items() for c in xs[: max(1, round(limit * share.get(k, 0.2)))]]
    for fc in svc.feedback.corrected_cases():
        cases.append({"id": f"fb-{abs(hash(fc['query'])) % 10000}", "kind": "valuation", "query": fc["query"], "expected_value": fc["expected_value"], "expected_intent": "valuation", "source": "feedback"})

    # Hold golden records out of the pricing model as well as the comparable pool.
    svc.pricing.refit_excluding({c["source_id"] for c in cases if c.get("source_id")})

    rows = []
    for c in cases:
        t0 = time.perf_counter()
        resp = run_pipeline(svc, c["query"], QueryFilters(), 8, exclude_ids={c["source_id"]} if c.get("source_id") else None)
        ms = int((time.perf_counter() - t0) * 1000)
        r = {"id": c["id"], "kind": c["kind"], "latency": ms, "blocked": not resp.guardrails.passed, "intent": resp.classification.intent if resp.classification else None}
        if c["kind"] == "guardrail":
            r["guardrail_ok"] = (not resp.guardrails.passed) == c["expected_blocked"]
        else:
            r["intent_ok"] = r["intent"] == c["expected_intent"]
            if resp.comparables:
                nb = c.get("expected_neighborhood")
                area = c.get("expected_area")
                rel = [cc for cc in resp.comparables if (nb is None or cc.property.neighborhood == nb) and (area is None or abs(cc.property.grLivArea - area) / area <= 0.25)]
                r["precision"] = len(rel) / len(resp.comparables)
                r["recall"] = min(1.0, len(rel) / 3)   # ≥3 relevant comps = full recall for appraisal purposes
                r["relevancy"] = float((nb is None or NEIGHBORHOOD_NAMES.get(nb, nb).split()[0] in resp.answer or nb in resp.answer) and ("$" in resp.answer or c["kind"] == "retrieval"))
                r["faithfulness"] = grounded_share(resp)
            if c["kind"] == "valuation" and resp.valuation:
                err = abs(resp.valuation.estimate - c["expected_value"]) / c["expected_value"]
                r["ape"] = err
                r["in_range"] = resp.valuation.low <= c["expected_value"] <= resp.valuation.high
                r["judge_agree"] = (resp.judge.verdict == "approved") == (err < 0.15)
        rows.append(r)

    def mean(key, kinds=None):
        xs = [x[key] for x in rows if key in x and (kinds is None or x["kind"] in kinds)]
        return statistics.fmean(xs) if xs else 0.0

    faith = mean("faithfulness")
    metrics = {
        "Faithfulness": faith, "Answer relevancy": mean("relevancy"), "Contextual precision": mean("precision"), "Contextual recall": mean("recall"),
        "Hallucination": 1 - faith, "Valuation MAPE": mean("ape"), "Range coverage": mean("in_range"), "Intent accuracy": mean("intent_ok"), "Guardrail accuracy": mean("guardrail_ok"),
    }
    def pass_rate(name):
        key = {"Faithfulness": "faithfulness", "Answer relevancy": "relevancy", "Contextual precision": "precision", "Contextual recall": "recall", "Valuation MAPE": "ape", "Range coverage": "in_range", "Intent accuracy": "intent_ok", "Guardrail accuracy": "guardrail_ok", "Hallucination": "faithfulness"}[name]
        xs = [x[key] for x in rows if key in x]
        if not xs:
            return 0.0
        th = THRESHOLDS[name]
        if name == "Hallucination":
            return sum(1 for v in xs if 1 - v <= th) / len(xs)
        if name == "Valuation MAPE":
            return sum(1 for v in xs if v <= th) / len(xs)
        return sum(1 for v in xs if float(v) >= th) / len(xs)

    lat = sorted(x["latency"] for x in rows)
    summary = {
        "runId": f"eval_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}", "ranAt": datetime.now(timezone.utc).isoformat(), "cases": len(rows),
        "metrics": [{"name": k, "score": round(v, 4), "threshold": THRESHOLDS[k], "passRate": round(pass_rate(k), 4)} for k, v in metrics.items()],
        "judgeAgreement": round(mean("judge_agree"), 4), "history": [], "feedback": svc.feedback.counts(),
        "latencyP50": lat[len(lat) // 2], "latencyP95": lat[min(len(lat) - 1, int(len(lat) * 0.95))], "source": "builtin" + ("+llm" if svc.llm.enabled else ""),
    }
    hist_path = ROOT / "results" / "history.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    history.append({"date": datetime.now(timezone.utc).strftime("%b %d"), "faithfulness": round(faith, 3), "relevancy": round(metrics["Answer relevancy"], 3), "precision": round(metrics["Contextual precision"], 3), "runId": summary["runId"]})
    summary["history"] = [{k: h[k] for k in ("date", "faithfulness", "relevancy", "precision")} for h in history[-8:]]
    if write:
        (ROOT / "results").mkdir(exist_ok=True)
        hist_path.write_text(json.dumps(history, indent=2))
        (ROOT / "results" / "latest.json").write_text(json.dumps(summary, indent=2))
        (ROOT / "results" / "cases_latest.json").write_text(json.dumps(rows, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "history"}, indent=2))
    failing = [m for m in summary["metrics"] if (m["score"] > m["threshold"]) if m["name"] in LOWER_IS_BETTER] + [m for m in summary["metrics"] if (m["score"] < m["threshold"]) if m["name"] not in LOWER_IS_BETTER]
    print("FAILING:" if failing else "ALL THRESHOLDS MET", [m["name"] for m in failing])
    return summary


if __name__ == "__main__":
    lim = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
    s = run(limit=lim)
    bad = [m for m in s["metrics"] if (m["score"] > m["threshold"] if m["name"] in LOWER_IS_BETTER else m["score"] < m["threshold"])]
    sys.stdout.flush()
    import os
    os._exit(1 if bad and "--no-fail" not in sys.argv else 0)  # skip interpreter teardown: onnxruntime threads can abort on exit
