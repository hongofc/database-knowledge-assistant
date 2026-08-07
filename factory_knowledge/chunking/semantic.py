"""Semantic chunking — split where the *meaning* shifts.

Instead of counting characters, this embeds each sentence and measures the
cosine similarity between consecutive sentences. A large drop in similarity
means the topic changed, so that gap becomes a chunk boundary.

Why it matters on a factory corpus: a troubleshooting page often runs
"symptom -> cause -> remedy -> next fault". Fixed-size chunking may cut
mid-remedy and glue the start of an unrelated fault onto it. Semantic
chunking cuts exactly at the fault-to-fault transition.

The breakpoint threshold is a *percentile* of the observed distance
distribution (default 85), which adapts to each document instead of relying
on a magic absolute number.

Embeddings come from :mod:`factory_knowledge.embeddings`, so this runs fully
local via Ollama/LM Studio, or falls back to the offline hashing embedder so
tests never need a network.
"""

from __future__ import annotations

import math

from ..rag.base import Chunk, Document
from .base import HEADING_RE, PAGE_RE, SENTENCE_RE, ChunkStrategy, register


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


@register
class SemanticChunker(ChunkStrategy):
    key = "semantic"
    label = "Semantic (embedding breakpoints)"
    description = "Embeds sentences and cuts where consecutive similarity drops sharply."

    def __init__(self, chunk_size: int = 800, overlap: int = 120,
                 embedder=None, breakpoint_percentile: float = 85.0,
                 min_sentences: int = 2, **kwargs) -> None:
        super().__init__(chunk_size, overlap, **kwargs)
        self.breakpoint_percentile = breakpoint_percentile
        self.min_sentences = min_sentences
        self._embedder = embedder

    @property
    def embedder(self):
        """Lazy: only construct/probe an embedder when we actually chunk."""
        if self._embedder is None:
            from ..embeddings import auto_embedder, build_embedder

            self._embedder = build_embedder(auto_embedder())
        return self._embedder

    def _sentences(self, text: str) -> list[str]:
        out: list[str] = []
        for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
            for sent in SENTENCE_RE.split(para):
                sent = sent.strip()
                if sent:
                    out.append(sent)
        return out

    def split(self, doc: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        for section, page, block in _blocks(doc.text):
            sentences = self._sentences(block)
            if len(sentences) <= self.min_sentences:
                chunk = self._chunk(block, doc, section, page, breakpoints=0)
                if chunk:
                    chunks.append(chunk)
                continue

            try:
                vectors = self.embedder.embed(sentences)
            except Exception:  # noqa: BLE001 - never let embedding kill ingest
                from ..embeddings import HashEmbedder

                vectors = HashEmbedder().embed(sentences)

            # Distance between neighbours; high distance = topic shift.
            distances = [
                1.0 - _cosine(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)
            ]
            threshold = _percentile(distances, self.breakpoint_percentile)

            buffer: list[str] = [sentences[0]]
            cuts = 0
            for i, dist in enumerate(distances):
                nxt = sentences[i + 1]
                current_len = sum(len(s) + 1 for s in buffer)
                # Cut on a genuine semantic break, or if we'd overflow the budget.
                if (dist >= threshold and len(buffer) >= self.min_sentences) or (
                    current_len + len(nxt) > self.chunk_size
                ):
                    chunk = self._chunk(
                        " ".join(buffer), doc, section, page,
                        breakpoints=cuts, sentences=len(buffer),
                    )
                    if chunk:
                        chunks.append(chunk)
                    cuts += 1
                    buffer = [nxt]
                else:
                    buffer.append(nxt)
            if buffer:
                chunk = self._chunk(
                    " ".join(buffer), doc, section, page,
                    breakpoints=cuts, sentences=len(buffer),
                )
                if chunk:
                    chunks.append(chunk)
        return chunks


def _blocks(text: str) -> list[tuple[str, int | None, str]]:
    """Group text into (section, page, body) so provenance survives chunking."""
    out: list[tuple[str, int | None, str]] = []
    section, page = "", None
    buffer: list[str] = []

    def flush() -> None:
        body = "\n\n".join(buffer).strip()
        if body:
            out.append((section, page, body))

    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        page_match = PAGE_RE.match(para)
        if page_match:
            flush()
            buffer = []
            page = int(page_match.group(1))
            continue
        heading = HEADING_RE.match(para.splitlines()[0].strip())
        if heading:
            flush()
            buffer = [para]
            section = heading.group(2).strip()
            continue
        buffer.append(para)
    flush()
    return out
