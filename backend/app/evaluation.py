"""Serve the latest evaluation run. Results are produced offline by
evals/run_eval.py (built-in metrics, no API key) or evals/run_deepeval.py
(DeepEval suite) and written to evals/results/latest.json; feedback counts are
live from the database."""
from __future__ import annotations

import json
from pathlib import Path

from app.schemas import EvalFeedback, EvalSummary


def load_latest(path: Path, feedback_counts: dict, latency: dict) -> EvalSummary:
    if path.exists():
        data = json.loads(path.read_text())
        data["feedback"] = feedback_counts
        if latency.get("p50"):
            data["latencyP50"], data["latencyP95"] = latency["p50"], latency["p95"]
        return EvalSummary(**data)
    return EvalSummary(
        runId="none", ranAt="", cases=0, metrics=[], judgeAgreement=0.0, history=[], feedback=EvalFeedback(**feedback_counts),
        latencyP50=latency.get("p50") or 0, latencyP95=latency.get("p95") or 0, source="none",
    )
