"""DeepEval suite — LLM-graded recommendation quality.

Requires ANTHROPIC_API_KEY (DeepEval uses Claude as the grader). Runs the same
golden set as run_eval.py through the pipeline, builds LLMTestCases where the
`retrieval_context` is the exact comparable records the answer was grounded on,
and scores Faithfulness, Answer Relevancy, Contextual Precision / Recall and
Hallucination, plus a custom ValuationMAPE metric. Writes results in the same
shape as run_eval.py so the UI can show either run.

    pip install -r requirements-eval.txt
    python evals/run_deepeval.py            # writes evals/results/latest.json (source="deepeval")
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402
from app.graph import run_pipeline  # noqa: E402
from app.schemas import QueryFilters  # noqa: E402
from app.services import Services  # noqa: E402

ROOT = Path(__file__).parent


class ValuationMAPE:  # lazily subclassed below so importing this file never requires deepeval
    pass


def main(limit: int | None = None) -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is required for DeepEval grading (Claude is the grader). Use evals/run_eval.py for the key-free suite.")
    from deepeval import evaluate
    from deepeval.evaluate.configs import AsyncConfig, DisplayConfig
    from deepeval.metrics import AnswerRelevancyMetric, BaseMetric, ContextualPrecisionMetric, ContextualRecallMetric, FaithfulnessMetric, HallucinationMetric
    from deepeval.models import AnthropicModel
    from deepeval.test_case import LLMTestCase

    class ValuationMAPEMetric(BaseMetric):
        """Deterministic metric: absolute percentage error vs. the hold-out sale price."""

        def __init__(self, threshold: float = 0.15):
            self.threshold = threshold

        def measure(self, test_case: LLMTestCase) -> float:
            meta = test_case.additional_metadata or {}
            est, exp = meta.get("estimate"), meta.get("expected_value")
            if not est or not exp:
                self.score, self.success, self.reason = 1.0, True, "not a valuation case"
                return self.score
            ape = abs(est - exp) / exp
            self.score = max(0.0, 1 - ape / self.threshold)  # 1.0 = exact, 0.0 = at/over threshold
            self.success = ape <= self.threshold
            self.reason = f"estimate {est:,} vs actual {exp:,} → APE {ape:.1%}"
            return self.score

        async def a_measure(self, test_case: LLMTestCase) -> float:
            return self.measure(test_case)

        def is_successful(self) -> bool:
            return bool(self.success)

        @property
        def __name__(self):
            return "Valuation MAPE"

    grader = AnthropicModel(model=os.getenv("DEEPEVAL_MODEL", "claude-opus-5-5"))
    svc = Services(get_settings())
    cases = [c for c in json.loads((ROOT / "golden_set.json").read_text())["cases"] if c["kind"] != "guardrail"]
    if limit:
        cases = cases[:limit]
    svc.pricing.refit_excluding({c["source_id"] for c in cases if c.get("source_id")})  # honest hold-out, as in run_eval.py

    tests: list[LLMTestCase] = []
    latencies: list[int] = []
    for c in cases:
        t0 = time.perf_counter()
        resp = run_pipeline(svc, c["query"], QueryFilters(), 8, exclude_ids={c["source_id"]} if c.get("source_id") else None)
        latencies.append(int((time.perf_counter() - t0) * 1000))
        ctx = [cc.property.summary for cc in resp.comparables]
        expected = (
            f"A valuation near ${c['expected_value']:,} for a home in {c['expected_neighborhood']} grounded in comparable sales from the same neighborhood."
            if c["kind"] == "valuation" else f"Comparable sales from {c['expected_neighborhood']} matching the stated attributes."
        )
        tests.append(LLMTestCase(
            input=c["query"], actual_output=resp.answer + "\n\n" + (resp.valuation.narrative if resp.valuation else ""), expected_output=expected,
            retrieval_context=ctx, context=ctx, name=c["id"],
            additional_metadata={"estimate": resp.valuation.estimate if resp.valuation else None, "expected_value": c.get("expected_value"), "judge": resp.judge.verdict if resp.judge else None},
        ))

    metrics = [
        FaithfulnessMetric(threshold=0.85, model=grader), AnswerRelevancyMetric(threshold=0.8, model=grader),
        ContextualPrecisionMetric(threshold=0.7, model=grader), ContextualRecallMetric(threshold=0.7, model=grader),
        HallucinationMetric(threshold=0.1, model=grader), ValuationMAPEMetric(0.15),
    ]
    # Gateways rate-limit aggressively: grade with low concurrency instead of DeepEval's default 20.
    result = evaluate(test_cases=tests, metrics=metrics, async_config=AsyncConfig(run_async=True, max_concurrent=int(os.getenv("DEEPEVAL_CONCURRENCY", "2")), throttle_value=1), display_config=DisplayConfig(show_indicator=True, print_results=False, inspect_after_run=False))

    # Aggregate into the shared results shape.
    per_metric: dict[str, list[tuple[float, bool]]] = {}
    for tr in result.test_results:
        for md in tr.metrics_data or []:
            per_metric.setdefault(md.name, []).append((md.score or 0.0, bool(md.success)))
    name_map = {"Faithfulness": "Faithfulness", "Answer Relevancy": "Answer relevancy", "Contextual Precision": "Contextual precision", "Contextual Recall": "Contextual recall", "Hallucination": "Hallucination", "Valuation MAPE": "Valuation MAPE"}
    thresholds = {"Faithfulness": 0.85, "Answer relevancy": 0.8, "Contextual precision": 0.7, "Contextual recall": 0.7, "Hallucination": 0.1, "Valuation MAPE": 0.15}
    out_metrics = []
    for raw, nice in name_map.items():
        xs = per_metric.get(raw, [])
        if not xs:
            continue
        score = statistics.fmean(s for s, _ in xs)
        if nice == "Valuation MAPE":  # convert the 0-1 closeness score back to an error
            apes = [abs(t.additional_metadata["estimate"] - t.additional_metadata["expected_value"]) / t.additional_metadata["expected_value"] for t in tests if t.additional_metadata.get("expected_value")]
            score = statistics.fmean(apes) if apes else 0.0
        out_metrics.append({"name": nice, "score": round(score, 4), "threshold": thresholds[nice], "passRate": round(sum(1 for _, ok in xs if ok) / len(xs), 4)})

    agree = [(t.additional_metadata["judge"] == "approved") == (abs(t.additional_metadata["estimate"] - t.additional_metadata["expected_value"]) / t.additional_metadata["expected_value"] < 0.15) for t in tests if t.additional_metadata.get("expected_value")]
    lat = sorted(latencies)
    faith = next((m["score"] for m in out_metrics if m["name"] == "Faithfulness"), 0.0)
    summary = {
        "runId": f"deepeval_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}", "ranAt": datetime.now(timezone.utc).isoformat(), "cases": len(tests), "metrics": out_metrics,
        "judgeAgreement": round(statistics.fmean(agree), 4) if agree else 0.0, "history": [], "feedback": svc.feedback.counts(),
        "latencyP50": lat[len(lat) // 2], "latencyP95": lat[min(len(lat) - 1, int(len(lat) * 0.95))], "source": "deepeval",
    }
    hist_path = ROOT / "results" / "history.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    history.append({"date": datetime.now(timezone.utc).strftime("%b %d"), "faithfulness": round(faith, 3), "relevancy": round(next((m["score"] for m in out_metrics if m["name"] == "Answer relevancy"), 0.0), 3), "precision": round(next((m["score"] for m in out_metrics if m["name"] == "Contextual precision"), 0.0), 3), "runId": summary["runId"]})
    summary["history"] = [{k: h[k] for k in ("date", "faithfulness", "relevancy", "precision")} for h in history[-8:]]
    (ROOT / "results").mkdir(exist_ok=True)
    hist_path.write_text(json.dumps(history, indent=2))
    (ROOT / "results" / "latest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
    sys.stdout.flush()
    os._exit(0)  # skip interpreter teardown: onnxruntime threads can abort on exit
