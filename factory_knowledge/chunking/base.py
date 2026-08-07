"""Chunking strategy interface + registry.

Chunking is the highest-leverage knob in RAG: the retriever can only ever
return what the chunker produced. A boundary in the wrong place splits an
error-code row from its remedy, or glues an unrelated section onto a safety
procedure — and no amount of embedding quality recovers that.

Every strategy implements one method::

    split(doc: Document) -> list[Chunk]

so they are interchangeable and directly comparable in the evaluation harness.
Select one with ``CHUNK_STRATEGY`` in ``.env``.
"""

from __future__ import annotations

import abc
import re

from ..rag.base import Chunk, Document

# Shared parsing helpers used by several strategies.
PAGE_MARKER = "<<<PAGE:{n}>>>"
PAGE_RE = re.compile(r"^<<<PAGE:(\d+)>>>$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# A markdown/flattened table row: "| a | b |" or "a | b | c".
TABLE_ROW_RE = re.compile(r"^\s*\|?[^|\n]+\|[^|\n]+")
# Sentence boundary that tolerates codes like "E-204." and "No. 5".
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


class ChunkStrategy(abc.ABC):
    """Base class for every chunking strategy."""

    key: str = "base"
    label: str = "Base"
    description: str = ""

    def __init__(self, chunk_size: int = 800, overlap: int = 120, **kwargs) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.options = kwargs

    @abc.abstractmethod
    def split(self, doc: Document) -> list[Chunk]:
        """Split one document into retrievable chunks."""

    # -- helpers shared by subclasses ---------------------------------------
    def _chunk(self, text: str, doc: Document, section: str = "",
               page: int | None = None, **extra) -> Chunk | None:
        """Build a Chunk, attaching provenance + strategy metadata."""
        text = text.strip()
        if not text:
            return None
        meta: dict = {"strategy": self.key}
        if section:
            meta["section"] = section
        if page is not None:
            meta["page"] = page
        meta.update(extra)
        return Chunk(text=text, source=doc.source, role=doc.role, metadata=meta)

    def _overlap_tail(self, text: str) -> str:
        """Trailing slice of ``text`` for overlap, trimmed to a word boundary."""
        if not self.overlap or not text:
            return ""
        tail = text[-self.overlap:]
        return tail[tail.find(" ") + 1:] if " " in tail else tail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{type(self).__name__} size={self.chunk_size} overlap={self.overlap}>"


_REGISTRY: dict[str, type[ChunkStrategy]] = {}


def register(cls: type[ChunkStrategy]) -> type[ChunkStrategy]:
    """Decorator: add a strategy to the registry under its ``key``."""
    _REGISTRY[cls.key] = cls
    return cls


def build_strategy(key: str, **kwargs) -> ChunkStrategy:
    """Factory: strategy key -> configured instance."""
    from . import metadata_aware, recursive, semantic, simple  # noqa: F401 - register

    cls = _REGISTRY.get((key or "fixed").lower())
    if cls is None:
        raise ValueError(
            f"Unknown chunk strategy {key!r}. Available: {', '.join(sorted(_REGISTRY))}"
        )
    return cls(**kwargs)


def available_strategies() -> dict[str, str]:
    """Map of key -> description, for the UI and CLI help."""
    from . import metadata_aware, recursive, semantic, simple  # noqa: F401 - register

    return {k: c.description for k, c in sorted(_REGISTRY.items())}
