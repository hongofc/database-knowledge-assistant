"""Pure-Python BM25 retriever — the zero-dependency default.

BM25 is the classic, strong keyword-ranking algorithm used by search engines.
It needs no model, no API, and no network, so the kit works the moment you
clone it. It is a great baseline to compare your vector retriever against later.

When you are ready for semantic search (matching meaning, not just words — e.g.
"machine won't start" finding "spindle fails to spin up"), set ``RETRIEVER=vector``
to switch to :class:`VectorRetriever`.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .base import Chunk, Retriever

# A small English stop-word list. Trimming these sharpens keyword matching.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for",
    "from", "how", "i", "if", "in", "into", "is", "it", "its", "of", "on", "or",
    "that", "the", "this", "to", "was", "what", "when", "where", "which", "who",
    "will", "with", "you", "your", "we", "our", "my", "me", "have", "has",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stop-words.

    Note that alphanumeric tokens keep part/error codes like ``e204`` or
    ``m12`` intact, which matters a lot for technical retrieval.
    """
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class KeywordRetriever(Retriever):
    """In-memory BM25 ranking over chunk tokens.

    Parameters ``k1`` and ``b`` are the standard BM25 knobs; the defaults are
    well-tested general-purpose values.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._chunks: list[Chunk] = []
        self._token_freqs: list[Counter] = []  # per-chunk term frequencies
        self._doc_freq: Counter = Counter()  # how many chunks contain a term
        self._avg_len: float = 0.0

    def index(self, chunks: list[Chunk]) -> None:
        self._chunks = list(chunks)
        self._token_freqs = []
        self._doc_freq = Counter()
        total_len = 0
        for chunk in self._chunks:
            tokens = tokenize(chunk.text)
            tf = Counter(tokens)
            self._token_freqs.append(tf)
            total_len += len(tokens)
            for term in tf:
                self._doc_freq[term] += 1
        n = len(self._chunks)
        self._avg_len = (total_len / n) if n else 0.0

    def _idf(self, term: str) -> float:
        """BM25 inverse document frequency (with the usual +0.5 smoothing)."""
        n = len(self._chunks)
        df = self._doc_freq.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def retrieve(self, query: str, top_k: int = 5) -> list[Chunk]:
        if not self._chunks:
            return []
        q_terms = tokenize(query)
        scored: list[Chunk] = []
        for chunk, tf in zip(self._chunks, self._token_freqs):
            doc_len = sum(tf.values()) or 1
            score = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                freq = tf[term]
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (
                    1 - self.b + self.b * doc_len / (self._avg_len or 1)
                )
                score += self._idf(term) * (numerator / denominator)
            if score > 0:
                # Return a copy (preserving section/page metadata) so callers
                # can set score without mutating the indexed chunk.
                scored.append(
                    Chunk(
                        text=chunk.text,
                        source=chunk.source,
                        role=chunk.role,
                        score=round(score, 4),
                        metadata=dict(chunk.metadata),
                    )
                )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    def __len__(self) -> int:
        return len(self._chunks)
