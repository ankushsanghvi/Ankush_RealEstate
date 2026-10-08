"""Dense embedding backends.

Primary: fastembed (ONNX, BAAI/bge-small-en-v1.5, 384-d) — a real neural
sentence encoder that runs on CPU without torch.
Fallback: LSA (TF-IDF → truncated SVD) — pure scikit-learn, always available.
Both expose the same tiny interface so the index never cares which one it got."""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


class Embedder:
    name: str = "base"
    dim: int = 0

    def fit(self, texts: list[str]) -> None:  # LSA needs a fit; neural models don't.
        pass

    def encode(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class FastEmbedEmbedder(Embedder):
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding  # imported lazily so the fallback works without it

        self._model = TextEmbedding(model_name)
        self.name = f"fastembed:{model_name}"
        self.dim = len(next(iter(self._model.embed(["probe"]))))

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = np.asarray(list(self._model.embed(texts, batch_size=64)), dtype=np.float32)
        return _l2(vecs)


class LSAEmbedder(Embedder):
    def __init__(self, dim: int = 256):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import make_pipeline

        self._pipe = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2), TruncatedSVD(dim, random_state=0))
        self.name = f"lsa:tfidf-svd-{dim}"
        self.dim = dim

    def fit(self, texts: list[str]) -> None:
        self._pipe.fit(texts)

    def encode(self, texts: list[str]) -> np.ndarray:
        return _l2(np.asarray(self._pipe.transform(texts), dtype=np.float32))


def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.clip(n, 1e-9, None)


def build_embedder(backend: str, model_name: str) -> Embedder:
    if backend == "fastembed":
        try:
            return FastEmbedEmbedder(model_name)
        except Exception as e:  # model download blocked, missing wheel, etc.
            log.warning("fastembed unavailable (%s); falling back to LSA embeddings", e)
    return LSAEmbedder()
