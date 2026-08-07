"""The retrieval interface that the whole kit depends on.

Keeping this surface tiny is what makes the RAG layer swappable: any class
that can ``index`` chunks and ``retrieve`` the most relevant ones is a valid
retriever. The orchestrator and agents only ever see these methods.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class Document:
    """A source file loaded from disk before it is split into chunks."""

    text: str
    source: str  # e.g. "data/maintenance/error_code_reference.md"
    role: str  # which specialist this document belongs to, e.g. "maintenance"


@dataclass
class Chunk:
    """A retrievable slice of a document, plus its provenance.

    ``metadata`` may carry ``section`` (nearest heading) and ``page`` (for PDFs),
    which power the verifiable citations that factory technicians can check
    against the official document.
    """

    text: str
    source: str
    role: str
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def citation(self) -> str:
        """Human-readable provenance, e.g. ``manual.pdf (p.3) > Troubleshooting``."""
        ref = self.source
        page = self.metadata.get("page")
        section = self.metadata.get("section")
        if page is not None:
            ref += f" (p.{page})"
        if section:
            ref += f" > {section}"
        return ref


class Retriever(abc.ABC):
    """Minimal contract every retriever must satisfy.

    Implement these two methods and your retriever drops straight into the
    rest of the application.
    """

    @abc.abstractmethod
    def index(self, chunks: list[Chunk]) -> None:
        """Store chunks so they can be searched later."""

    @abc.abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list[Chunk]:
        """Return up to ``top_k`` chunks most relevant to ``query``.

        Returned chunks should carry a populated ``score`` (higher = better).
        """

    # Convenience used by the agents; override if your store handles it natively.
    def __len__(self) -> int:  # pragma: no cover - trivial
        return 0


def build_retriever(kind: str, **kwargs) -> Retriever:
    """Factory: turn a config string into a concrete retriever.

    This is the single place that knows about concrete retriever classes, so
    adding a new backend means adding one ``elif`` here.
    """
    kind = (kind or "keyword").lower()
    if kind == "keyword":
        from .keyword_retriever import KeywordRetriever

        return KeywordRetriever(**kwargs)
    if kind == "vector":
        from .vector_retriever import VectorRetriever

        return VectorRetriever(**kwargs)
    if kind == "hybrid":
        from .hybrid_retriever import HybridRetriever

        return HybridRetriever(**kwargs)
    raise ValueError(
        f"Unknown retriever kind: {kind!r}. Use 'keyword', 'vector', or 'hybrid', "
        "or register your own here."
    )
