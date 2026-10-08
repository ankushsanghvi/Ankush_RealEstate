"""Hybrid retrieval: BM25 (keyword) ∪ dense cosine (semantic), fused with
reciprocal-rank fusion, then metadata-filtered.

Dense vectors live in a FAISS exact inner-product index (`vector_store.py`);
metadata filters are pushed into the FAISS search as an ID selector, and BM25
is restricted to the same allowed set, so both rankings respect the hard
constraints before fusion."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from app.data.loader import Dataset, NEIGHBORHOOD_NAMES, apply_filters
from app.retrieval.embedder import Embedder, build_embedder
from app.retrieval.vector_store import VectorStore
from app.schemas import Property, QueryFilters

log = logging.getLogger(__name__)
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    text = text.lower().replace(",", "")
    toks = _TOKEN.findall(text)
    # Expand neighborhood codes so "collgcr" and "college creek" both match.
    extra: list[str] = []
    for code, name in NEIGHBORHOOD_NAMES.items():
        if code.lower() in text or name.lower() in text:
            extra += [code.lower()] + _TOKEN.findall(name.lower())
    return toks + extra


@dataclass
class Hit:
    property: Property
    semantic: float
    keyword: float
    hybrid: float


class HybridIndex:
    def __init__(self, ds: Dataset, backend: str, model_name: str, cache_dir: Path, rrf_k: int = 60, dense_weight: float = 0.65):
        self.ds = ds
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        texts = [p.summary for p in ds.properties]
        t0 = time.perf_counter()
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])
        self.embedder: Embedder = build_embedder(backend, model_name)
        self.matrix = self._load_or_embed(texts, cache_dir)
        self.store = VectorStore(self.matrix)
        log.info("index ready: %d docs, embedder=%s, store=%s, %.1fs", len(texts), self.embedder.name, self.store.name, time.perf_counter() - t0)

    def _load_or_embed(self, texts: list[str], cache_dir: Path) -> np.ndarray:
        key = hashlib.sha1((self.embedder.name + "|" + "\n".join(texts)).encode()).hexdigest()[:16]
        path = cache_dir / f"emb_{key}.npy"
        if path.exists():
            return np.load(path)
        self.embedder.fit(texts)
        m = self.embedder.encode(texts)
        np.save(path, m)
        return m

    def search(self, query: str, filters: QueryFilters, top_k: int = 10, pool: int = 40, exclude_ids: set[str] | None = None) -> tuple[list[Hit], int]:
        """Returns (hits, candidate_pool_size_after_filter). `exclude_ids` supports
        hold-out evaluation: the subject record is removed from its own comparables."""
        allowed_ids = {p.id for p in apply_filters(self.ds.properties, filters)} - (exclude_ids or set())
        allowed_idx = np.fromiter((i for i, p in enumerate(self.ds.properties) if p.id in allowed_ids), dtype=np.int64)
        if len(allowed_idx) == 0:
            return [], 0

        q_dense = self.embedder.encode([query])[0]
        kw_all = np.asarray(self.bm25.get_scores(tokenize(query)), dtype=np.float32)
        kw = kw_all[allowed_idx]
        n = min(pool, len(allowed_idx))
        sem_ids, _ = self.store.search(q_dense, n, allowed_idx)       # global row ids, best first
        kw_ids = allowed_idx[np.argsort(-kw, kind="stable")[:n]]

        fused: dict[int, float] = {}
        for r, gi in enumerate(sem_ids):
            fused[int(gi)] = fused.get(int(gi), 0.0) + self.dense_weight / (self.rrf_k + r + 1)
        for r, gi in enumerate(kw_ids):
            fused[int(gi)] = fused.get(int(gi), 0.0) + (1 - self.dense_weight) / (self.rrf_k + r + 1)

        kw_max = float(kw.max()) if kw.size and kw.max() > 0 else 1.0
        f_max = max(fused.values()) if fused else 1.0
        top = sorted(fused.items(), key=lambda kv: -kv[1])[:top_k]
        sem_top = self.store.scores(q_dense, np.array([gi for gi, _ in top], dtype=np.int64))
        hits = []
        for (gi, score), cos in zip(top, sem_top):
            hits.append(Hit(
                property=self.ds.properties[gi],
                semantic=float(np.clip((cos + 1) / 2, 0, 1)),   # map cosine [-1,1] → [0,1]
                keyword=float(kw_all[gi] / kw_max),
                hybrid=float(score / f_max),
            ))
        return hits, int(len(allowed_idx))
