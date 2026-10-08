"""Runtime configuration. Everything comes from environment variables so the same
image runs locally, in CI and on Render without code changes."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    app_name: str = "Valora API"
    version: str = "1.0.0"
    data_path: Path = ROOT / "data" / "ames_housing.arff"
    cache_dir: Path = ROOT / "data" / "cache"
    db_path: Path = Path(os.getenv("DB_PATH") or (ROOT / "data" / "valora.db"))
    eval_results_path: Path = ROOT / "evals" / "results" / "latest.json"

    # LLM — optional. Without a key the pipeline runs fully heuristic ("rules" mode).
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    anthropic_base_url: str | None = os.getenv("ANTHROPIC_BASE_URL") or None   # e.g. an Anthropic-compatible gateway
    llm_model: str = os.getenv("LLM_MODEL", "claude-opus-5-5")
    llm_fallback_model: str = os.getenv("LLM_FALLBACK_MODEL", "claude-sonnet-5-5")
    llm_fast_model: str | None = os.getenv("LLM_FAST_MODEL") or None   # used for cheap, latency-sensitive steps (classification)
    llm_structured_output: str = os.getenv("LLM_STRUCTURED_OUTPUT", "auto")  # auto | native | json
    llm_api_format: str = os.getenv("LLM_API_FORMAT", "messages")  # messages (Anthropic SDK) | chat (OpenAI-style /v1/chat/completions on a gateway)
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "25"))
    llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"

    # Retrieval
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "fastembed")  # fastembed | lsa
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    candidate_pool: int = int(os.getenv("CANDIDATE_POOL", "40"))
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    dense_weight: float = float(os.getenv("DENSE_WEIGHT", "0.65"))

    # API
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    max_query_chars: int = int(os.getenv("MAX_QUERY_CHARS", "600"))


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.cache_dir.mkdir(parents=True, exist_ok=True)
    s.eval_results_path.parent.mkdir(parents=True, exist_ok=True)
    return s
