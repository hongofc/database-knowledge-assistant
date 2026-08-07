"""Central configuration.

Values are read from environment variables (optionally via a local ``.env``
file) so you never hard-code secrets. Copy ``.env.example`` to ``.env`` and
fill in your OpenAI key, or reuse the same key as the Office Navigator kit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Project paths -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ROLES_FILE = PROJECT_ROOT / "roles.yaml"


def _load_dotenv() -> None:
    """Load key=value pairs from a ``.env`` file if present.

    Implemented by hand so the kit has zero required dependencies just to read
    configuration. ``python-dotenv`` would also work if you prefer it.
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value:
            # A real value in .env wins, even over a stale variable already in
            # the environment (a common "I edited .env but nothing changed" trap).
            os.environ[key] = value
        else:
            # Empty entries (the template defaults) must not clobber a real
            # environment variable, so they only act as a fallback default.
            os.environ.setdefault(key, value)


_load_dotenv()


def _default_min_score(retriever: str | None = None) -> float:
    """Scale-appropriate abstain floor for the active retriever.

    Measured on the sample corpus (see eval/run_eval.py):
      keyword/BM25 — grounded 4.3-16.0, adversarial 2.9-6.6  -> floor 4.0
      vector/cosine — grounded 0.64-0.85, adversarial 0.50-0.67 -> floor 0.68
    Neither is cleanly separable: the ranges OVERLAP, so any floor trades a
    false-abstain against a false-answer. These values are the measured best
    compromise, not a guarantee. Embeddings in particular cannot distinguish
    near-identical codes (Z-999 vs E-204), so a plausible-looking unknown code
    scores like a real one — the prompt-level guardrail is the backstop there.

    ``retriever`` is an explicit override so callers that switch retriever at
    runtime (the Streamlit sidebar) get the right floor for the retriever they
    just picked, instead of the one that happened to be set at import time.
    """
    retriever = (retriever or os.getenv("RETRIEVER", "keyword")).lower()
    return {"keyword": 4.0, "vector": 0.68, "hybrid": 0.0}.get(retriever, 0.0)


# Scoring scale of each retriever, for UI slider bounds and explanations.
# BM25 is unbounded (corpus-dependent); cosine similarity is bounded 0-1.
SCORE_SCALES = {
    "keyword": {"min": 0.0, "max": 20.0, "step": 0.5, "scale": "BM25 relevance (unbounded, typically 0-16 here)"},
    "vector": {"min": 0.0, "max": 1.0, "step": 0.01, "scale": "cosine similarity (0-1)"},
    "hybrid": {"min": 0.0, "max": 1.0, "step": 0.01, "scale": "reciprocal-rank fusion (small values)"},
}


@dataclass
class Settings:
    """Runtime settings, populated from the environment with sane defaults."""

    # --- LLM ---------------------------------------------------------------
    # Provider is a string so you can later add "gemini", "ollama", etc.
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    openai_api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    chat_model: str = field(default_factory=lambda: os.getenv("CHAT_MODEL", "gpt-4o-mini"))
    temperature: float = field(default_factory=lambda: float(os.getenv("TEMPERATURE", "0.1")))

    # --- Retrieval (RAG) ---------------------------------------------------
    # "keyword" = pure-Python BM25 (default, no deps). "vector" = ChromaDB.
    retriever: str = field(default_factory=lambda: os.getenv("RETRIEVER", "keyword"))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", "5")))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "800")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "120")))

    # --- Advanced chunking -------------------------------------------------
    # "fixed" (baseline) | "recursive" | "semantic" | "metadata_aware"
    chunk_strategy: str = field(
        default_factory=lambda: os.getenv("CHUNK_STRATEGY", "metadata_aware")
    )
    # Percentile of sentence-distance used as the semantic breakpoint.
    breakpoint_percentile: float = field(
        default_factory=lambda: float(os.getenv("BREAKPOINT_PERCENTILE", "85"))
    )

    # --- Embeddings --------------------------------------------------------
    # "auto" probes local-first: ollama > lmstudio > openai > hash.
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "auto")
    )

    # --- Persistence -------------------------------------------------------
    chroma_path: str = field(
        default_factory=lambda: os.getenv("CHROMA_PATH", str(PROJECT_ROOT / ".chroma"))
    )
    sessions_db: str = field(
        default_factory=lambda: os.getenv("SESSIONS_DB", str(PROJECT_ROOT / ".sessions.db"))
    )

    # --- Hallucination guardrail ------------------------------------------
    # Minimum retrieval score required to trust a chunk. Below this for every
    # hit, the assistant abstains instead of answering.
    #
    # CRITICAL: the two retrievers live on different score scales —
    #   keyword (BM25) is unbounded, typically 2-16 on this corpus
    #   vector  (cosine-derived) is bounded 0-1
    # so a single fixed floor cannot serve both. A BM25-tuned floor of 4.0
    # would reject *every* vector hit and abstain on all questions. When
    # MIN_SCORE is unset we pick a scale-appropriate default automatically.
    min_score: float = field(
        default_factory=lambda: float(os.getenv("MIN_SCORE") or _default_min_score())
    )

    # --- Routing -----------------------------------------------------------
    # "keyword" = lightweight scoring. "llm" = ask the model to classify.
    router: str = field(default_factory=lambda: os.getenv("ROUTER", "keyword"))

    @property
    def llm_enabled(self) -> bool:
        """True when we have what we need to call the LLM provider."""
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        # Local providers (e.g. ollama) do not need a key — extend as needed.
        return self.llm_provider in {"ollama"}


# A single shared instance is convenient for a starter kit. For tests or
# multi-tenant use you can construct your own Settings() instead.
settings = Settings()
