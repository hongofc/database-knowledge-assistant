"""Hybrid retriever — BM25 keyword + dense vector, fused.

Why hybrid: the two retrievers fail in opposite ways, and a factory corpus
needs both.

* **BM25** nails exact identifiers. A technician typing "E-204" must land on
  the E-204 row; embeddings blur near-identical codes (E-204 vs E-220).
* **Vector** handles paraphrase. "machine making a grinding noise" should find
  "abnormal bearing vibration" despite sharing no keywords.

Results are combined with **Reciprocal Rank Fusion** (RRF), which merges ranked
lists without needing the two score scales to be comparable — BM25 scores are
unbounded while cosine similarity sits in [0,1], so naive score addition would
let BM25 dominate. RRF uses *ranks only*, sidestepping that entirely::

    score(d) = sum over retrievers of  1 / (k + rank_r(d))

``k`` (default 60) damps the influence of any single list's top hit.
"""

from __future__ import annotations

from ..config import settings
from .base import Chunk, Retriever

RRF_K = 60


class HybridRetriever(Retriever):
    """Fuse keyword and vector retrieval via Reciprocal Rank Fusion."""

    def __init__(self, keyword_weight: float = 1.0, vector_weight: float = 1.0,
                 rrf_k: int = RRF_K, **kwargs) -> None:
        from .keyword_retriever import KeywordRetriever
        from .vector_retriever import VectorRetriever

        self.keyword = KeywordRetriever()
        self.rrf_k = rrf_k
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight
        try:
            self.vector: Retriever | None = VectorRetriever(**kwargs)
        except Exception as exc:  # noqa: BLE001 - degrade, never crash
            import warnings

            warnings.warn(
                f"Vector retriever unavailable ({exc}); hybrid falls back to keyword only.",
                stacklevel=2,
            )
            self.vector = None

    def index(self, chunks: list[Chunk]) -> None:
        self.keyword.index(chunks)
        if self.vector is not None:
            try:
                self.vector.index(chunks)
            except Exception as exc:  # noqa: BLE001
                import warnings

                warnings.warn(f"Vector indexing failed ({exc}); keyword only.", stacklevel=2)
                self.vector = None

    def retrieve(self, query: str, top_k: int = 5) -> list[Chunk]:
        # Over-fetch from each arm so fusion has candidates to work with.
        pool = max(top_k * 3, 10)
        runs: list[tuple[float, list[Chunk]]] = [
            (self.keyword_weight, self.keyword.retrieve(query, top_k=pool))
        ]
        if self.vector is not None:
            try:
                runs.append((self.vector_weight, self.vector.retrieve(query, top_k=pool)))
            except Exception:  # noqa: BLE001 - a failing arm must not break search
                pass

        fused: dict[str, float] = {}
        best: dict[str, Chunk] = {}
        for weight, results in runs:
            for rank, chunk in enumerate(results, start=1):
                key = f"{chunk.source}::{chunk.text[:120]}"
                fused[key] = fused.get(key, 0.0) + weight / (self.rrf_k + rank)
                # Keep whichever copy scored highest in its own arm.
                if key not in best or chunk.score > best[key].score:
                    best[key] = chunk

        ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        out: list[Chunk] = []
        for key, score in ordered:
            chunk = best[key]
            out.append(
                Chunk(
                    text=chunk.text,
                    source=chunk.source,
                    role=chunk.role,
                    # Rescale RRF into a readable range; keep the raw arm score too.
                    score=round(score * self.rrf_k, 4),
                    metadata={**chunk.metadata, "raw_score": chunk.score},
                )
            )
        return out

    def __len__(self) -> int:
        return len(self.keyword)
