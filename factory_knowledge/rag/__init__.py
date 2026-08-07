"""Retrieval-Augmented Generation (RAG) building blocks.

Everything here sits behind the small :class:`Retriever` interface in
``base.py``. Start with :class:`KeywordRetriever` (no dependencies). When you
outgrow it, switch ``RETRIEVER=vector`` in your ``.env`` to use
:class:`VectorRetriever` — the rest of the app is unchanged.
"""

from .base import Chunk, Document, Retriever, build_retriever

__all__ = ["Chunk", "Document", "Retriever", "build_retriever"]
