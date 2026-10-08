"""Process-wide singletons built once at startup."""
from __future__ import annotations

import logging
import time

from app.agents.impact import ImpactModel
from app.agents.llm import LLM
from app.agents.pricing import PricingModel
from app.config import Settings
from app.data.loader import Dataset, load_dataset
from app.feedback import FeedbackStore
from app.retrieval.index import HybridIndex

log = logging.getLogger(__name__)


class Services:
    def __init__(self, settings: Settings):
        t0 = time.perf_counter()
        self.settings = settings
        self.ds: Dataset = load_dataset(settings.data_path)
        self.index = HybridIndex(self.ds, settings.embedding_backend, settings.embedding_model, settings.cache_dir, settings.rrf_k, settings.dense_weight)
        self.pricing = PricingModel(self.ds, settings.cache_dir)
        self.impact = ImpactModel(self.ds)
        self.llm = LLM(settings)
        self.feedback = FeedbackStore(settings.db_path)
        f = self.ds.frame
        self.bounds = {
            "grLivArea": (int(f.grLivArea.min()), int(f.grLivArea.max())), "yearBuilt": (int(f.yearBuilt.min()), int(f.yearBuilt.max())),
            "overallQual": (1, 10), "bedrooms": (0, int(f.bedroomAbvGr.max())), "garageCars": (0, int(f.garageCars.max())),
            "totalBsmtSF": (0, int(f.totalBsmtSF.max())), "lotArea": (int(f.lotArea.min()), int(f.lotArea.max())), "fullBath": (0, int(f.fullBath.max())),
        }
        self.started_at = time.time()
        self.latencies: list[int] = []
        log.info("services ready in %.1fs (llm=%s)", time.perf_counter() - t0, self.llm.enabled)

    def record_latency(self, ms: int) -> None:
        self.latencies.append(ms)
        if len(self.latencies) > 500:
            self.latencies = self.latencies[-500:]

    def latency_stats(self) -> dict:
        if not self.latencies:
            return {"p50": None, "p95": None, "n": 0}
        xs = sorted(self.latencies)
        return {"p50": xs[len(xs) // 2], "p95": xs[min(len(xs) - 1, int(len(xs) * 0.95))], "n": len(xs)}
