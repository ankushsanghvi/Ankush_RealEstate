"""Vector store: FAISS exact inner-product index with metadata pre-filtering.

Rows are L2-normalised, so inner product = cosine. `IndexFlatIP` is exact (no
recall loss from approximation), which is the right call at 2.9k vectors; an
`IndexHNSWFlat` is a one-line swap if the corpus grows by orders of magnitude.
Metadata filters are applied *inside* the search through an `IDSelectorBatch`,
so the top-k is computed only over records that satisfy the hard constraints.

If faiss cannot be imported (exotic platform, missing wheel) the store falls
back to a numpy matrix product with identical results."""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, matrix: np.ndarray):
        self.matrix = np.ascontiguousarray(matrix, dtype=np.float32)
        self.size, self.dim = self.matrix.shape
        try:
            import faiss

            self._faiss = faiss
            self._index = faiss.IndexFlatIP(self.dim)
            self._index.add(self.matrix)
            self.name = f"faiss:IndexFlatIP({self.dim}d)"
        except Exception as e:  # pragma: no cover - depends on the platform
            log.warning("faiss unavailable (%s); using numpy exact search", e)
            self._faiss = None
            self._index = None
            self.name = f"numpy:exact({self.dim}d)"

    def search(self, query: np.ndarray, k: int, allowed: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Top-k (row ids, cosine scores) restricted to `allowed` row ids."""
        q = np.ascontiguousarray(query.reshape(1, -1), dtype=np.float32)
        n_allowed = self.size if allowed is None else len(allowed)
        k = min(k, n_allowed)
        if k <= 0:
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
        if self._index is not None:
            params = None
            if allowed is not None:
                params = self._faiss.SearchParameters(sel=self._faiss.IDSelectorBatch(np.asarray(allowed, dtype=np.int64)))
            scores, ids = self._index.search(q, k, params=params)
            keep = ids[0] >= 0
            return ids[0][keep].astype(np.int64), scores[0][keep]
        rows = np.arange(self.size) if allowed is None else np.asarray(allowed, dtype=np.int64)
        sims = self.matrix[rows] @ q[0]
        order = np.argsort(-sims)[:k]
        return rows[order], sims[order]

    def scores(self, query: np.ndarray, rows: np.ndarray) -> np.ndarray:
        """Cosine scores for specific rows (used to score keyword-only hits)."""
        return self.matrix[np.asarray(rows, dtype=np.int64)] @ query.astype(np.float32)
