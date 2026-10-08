"""Embedding-model benchmark (no API key required).

Compares candidate dense encoders on the golden set using the production
HybridIndex, both dense-only and fused with BM25, with no metadata filters so
the encoder alone decides what is retrieved. The subject record is excluded
from its own results (hold-out), exactly as in run_eval.py.

Metrics per encoder (top-10):
  precision@10   share of hits in the expected neighborhood with living area within 25 %
  hit@3          share of queries with at least 3 relevant hits (appraisal needs ≥3 comps)
  MRR            reciprocal rank of the first relevant hit
  comp APE       |median sale price of top-5 hits − true price| / true price (valuation cases)
  index s / query ms / dim

Usage:  python evals/benchmark_embeddings.py   → evals/results/embedding_benchmark.json"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402
from app.data.loader import load_dataset  # noqa: E402
from app.retrieval.index import HybridIndex  # noqa: E402
from app.schemas import QueryFilters  # noqa: E402

ROOT = Path(__file__).parent
CANDIDATES = [
    ("lsa", "tfidf-svd-256", "LSA (TF-IDF → SVD, 256-d)"),
    ("fastembed", "sentence-transformers/all-MiniLM-L6-v2", "all-MiniLM-L6-v2 (384-d)"),
    ("fastembed", "BAAI/bge-small-en-v1.5", "bge-small-en-v1.5 (384-d)"),
    ("fastembed", "BAAI/bge-base-en-v1.5", "bge-base-en-v1.5 (768-d)"),
]
TOP_K = 10


def relevant(p, case) -> bool:
    nb, area = case.get("expected_neighborhood"), case.get("expected_area")
    return (nb is None or p.neighborhood == nb) and (area is None or abs(p.grLivArea - area) / area <= 0.25)


def score(index: HybridIndex, cases: list[dict], dense_weight: float) -> dict:
    index.dense_weight = dense_weight
    prec, hit3, rr, ape, lat = [], [], [], [], []
    for c in cases:
        t0 = time.perf_counter()
        hits, _ = index.search(c["query"], QueryFilters(), top_k=TOP_K, exclude_ids={c["source_id"]} if c.get("source_id") else None)
        lat.append((time.perf_counter() - t0) * 1000)
        rel = [relevant(h.property, c) for h in hits]
        prec.append(sum(rel) / max(1, len(hits)))
        hit3.append(float(sum(rel) >= 3))
        rr.append(next((1 / (i + 1) for i, r in enumerate(rel) if r), 0.0))
        if c["kind"] == "valuation" and hits:
            med = statistics.median(h.property.salePrice for h in hits[:5])
            ape.append(abs(med - c["expected_value"]) / c["expected_value"])
    return {
        "precision@10": round(statistics.fmean(prec), 4), "hit@3": round(statistics.fmean(hit3), 4), "mrr": round(statistics.fmean(rr), 4),
        "compAPE": round(statistics.fmean(ape), 4) if ape else None, "queryMs": round(statistics.median(lat), 1),
    }


def main() -> None:
    s = get_settings()
    ds = load_dataset(s.data_path)
    cases = [c for c in json.loads((ROOT / "golden_set.json").read_text())["cases"] if c["kind"] in ("valuation", "retrieval") and c.get("expected_neighborhood")]
    out = {"cases": len(cases), "topK": TOP_K, "filters": "none", "results": []}

    bm25_only = None
    for backend, model, label in CANDIDATES:
        t0 = time.perf_counter()
        try:
            idx = HybridIndex(ds, backend, model, s.cache_dir, s.rrf_k, s.dense_weight)
        except Exception as e:  # model download blocked etc.
            print(f"skip {label}: {e}")
            continue
        build_s = time.perf_counter() - t0
        if backend == "fastembed" and not idx.embedder.name.startswith("fastembed"):
            print(f"skip {label}: fell back to {idx.embedder.name}")
            continue
        if bm25_only is None:
            bm25_only = score(idx, cases, dense_weight=0.0)
        row = {"encoder": label, "id": idx.embedder.name, "dim": idx.embedder.dim, "indexS": round(build_s, 1),
               "dense": score(idx, cases, 1.0), "hybrid": score(idx, cases, s.dense_weight)}
        out["results"].append(row)
        print(f"{label:32s} dense P@10 {row['dense']['precision@10']:.3f} MRR {row['dense']['mrr']:.3f} | hybrid P@10 {row['hybrid']['precision@10']:.3f} "
              f"hit@3 {row['hybrid']['hit@3']:.3f} compAPE {row['hybrid']['compAPE']:.3f} | {row['hybrid']['queryMs']} ms")
    out["bm25Only"] = bm25_only
    print(f"{'BM25 only':32s} P@10 {bm25_only['precision@10']:.3f} MRR {bm25_only['mrr']:.3f} hit@3 {bm25_only['hit@3']:.3f} compAPE {bm25_only['compAPE']:.3f}")
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "embedding_benchmark.json").write_text(json.dumps(out, indent=2))
    sys.stdout.flush()
    import os
    os._exit(0)  # onnxruntime threads can abort during interpreter teardown


if __name__ == "__main__":
    main()
