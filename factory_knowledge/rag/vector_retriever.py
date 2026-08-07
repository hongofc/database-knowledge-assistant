"""Semantic vector retriever — the enterprise upgrade path.

This swaps keyword matching for *meaning* matching using embeddings stored in
ChromaDB (a lightweight, local, file-backed vector database). For a factory
knowledge base this matters: a technician typing "machine making a grinding
noise" should find the "abnormal bearing vibration" procedure even though they
share no keywords.

It is optional — the kit runs fine on the keyword retriever until you enable it::

    pip install chromadb           # the vector store
    # embeddings come from OpenAI by default (needs OPENAI_API_KEY)
    RETRIEVER=vector               # in your .env

Embeddings default to OpenAI's ``text-embedding-3-small`` (cheap, good). To go
fully local and free (often required for confidential factory documentation),
install ``sentence-transformers`` and wire the branch in :meth:`_embed`.
"""

from __future__ import annotations

import hashlib

from ..config import settings
from .base import Chunk, Retriever


class VectorRetriever(Retriever):
    """ChromaDB-backed semantic retriever.

    Uses an in-memory Chroma collection by default so it needs no setup. Point
    it at a persistent path (see the commented client below) to keep your index
    between runs — important for large manual sets you don't want to re-embed.
    """

    def __init__(self, collection_name: str = "factory_knowledge",
                 embedder=None, persist: bool = False) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "VectorRetriever needs ChromaDB. Install it with:\n"
                "    pip install chromadb\n"
                "or keep using the default keyword retriever (RETRIEVER=keyword)."
            ) from exc

        # Persistent client keeps the index between runs so large manual sets
        # are embedded once, not on every start.
        if persist:
            self._client = chromadb.PersistentClient(path=settings.chroma_path)
        else:
            self._client = chromadb.Client()
        try:
            self._client.delete_collection(collection_name)
        except Exception:  # noqa: BLE001 - collection may not exist yet
            pass
        self._collection = self._client.create_collection(
            collection_name,
            # Cosine is the right metric for text embeddings. The default (L2)
            # on unnormalized vectors compresses all scores into a narrow band
            # (measured: 0.591-0.601 across unrelated chunks), which destroys
            # the ranking signal and starves rank-fusion in the hybrid retriever.
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = embedder

    @property
    def embedder(self):
        """Lazy, local-first embedder (see :mod:`factory_knowledge.embeddings`)."""
        if self._embedder is None:
            from ..embeddings import auto_embedder, build_embedder

            key = settings.embedding_provider
            self._embedder = build_embedder(auto_embedder() if key == "auto" else key)
        return self._embedder

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed in batches; fall back to the offline embedder on failure."""
        try:
            out: list[list[float]] = []
            for i in range(0, len(texts), 64):
                out.extend(self.embedder.embed(texts[i:i + 64]))
            return out
        except Exception:  # noqa: BLE001 - never let embedding kill the demo
            from ..embeddings import HashEmbedder

            return HashEmbedder().embed(texts)

    def index(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        texts = [c.text for c in chunks]
        embeddings = self._embed(texts)
        ids = [hashlib.md5(f"{c.source}:{i}".encode()).hexdigest() for i, c in enumerate(chunks)]
        # Persist all scalar metadata so citations AND the new chunking tags
        # (content_type, heading_path, codes, strategy) survive Chroma.
        metadatas = []
        for c in chunks:
            meta: dict = {"source": c.source, "role": c.role}
            for k, v in c.metadata.items():
                if isinstance(v, (str, int, float, bool)) and v != "":
                    meta[k] = v
            metadatas.append(meta)
        self._collection.add(
            ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas
        )

    def retrieve(self, query: str, top_k: int = 5) -> list[Chunk]:
        if self._collection.count() == 0:
            return []
        query_emb = self._embed([query])[0]
        res = self._collection.query(
            query_embeddings=[query_emb],
            n_results=min(top_k, self._collection.count()),
        )
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        # With hnsw:space=cosine Chroma returns cosine DISTANCE (0=identical).
        # 1-distance recovers true cosine similarity, preserving the spread
        # between good and bad matches instead of squashing it.
        dists = res.get("distances", [[]])[0]
        chunks: list[Chunk] = []
        for text, meta, dist in zip(docs, metas, dists):
            extra = {k: v for k, v in meta.items() if k not in ("source", "role")}
            chunks.append(
                Chunk(
                    text=text,
                    source=meta.get("source", "?"),
                    role=meta.get("role", "?"),
                    score=round(max(0.0, 1.0 - float(dist)), 4),
                    metadata=extra,
                )
            )
        return chunks

    def __len__(self) -> int:
        return self._collection.count()
