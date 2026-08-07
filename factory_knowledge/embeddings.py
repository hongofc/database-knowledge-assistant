"""Pluggable embedding backends (local-first, API fallback).

Used by the semantic chunker and the vector retriever. Mirrors the LLM
provider design: one interface, several backends, live availability probing —
so confidential factory documents can stay on-prem while still allowing a
hosted fallback when local inference is too slow.
"""

from __future__ import annotations

import os

from .providers import Availability, _http_json


class Embedder:
    """Turn texts into vectors."""

    key = "base"
    label = "Base"
    is_local = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def available(self) -> Availability:
        raise NotImplementedError


class OllamaEmbedder(Embedder):
    """Local embeddings via Ollama (default: nomic-embed-text, 768-dim)."""

    key = "ollama"
    label = "Ollama (local)"
    is_local = True

    def __init__(self, model: str = "nomic-embed-text", host: str | None = None) -> None:
        self.model = model
        self.host = (host or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")

    def available(self) -> Availability:
        try:
            data = _http_json(f"{self.host}/api/tags")
        except Exception as exc:  # noqa: BLE001
            return Availability(False, f"Ollama not reachable ({exc})")
        names = [m.get("name", "") for m in data.get("models", [])]
        embed_models = [n for n in names if "embed" in n.lower()]
        if not embed_models:
            return Availability(
                False, "No embedding model in Ollama. Run: ollama pull nomic-embed-text"
            )
        return Availability(True, f"Ollama embeddings at {self.host}", sorted(embed_models))

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Ollama's OpenAI-compatible endpoint accepts a batch in one call.
        data = _http_json(
            f"{self.host}/v1/embeddings",
            {"model": self.model, "input": texts},
            timeout=300.0,
        )
        return [d["embedding"] for d in data["data"]]


class LMStudioEmbedder(Embedder):
    """Local embeddings via LM Studio's OpenAI-compatible server."""

    key = "lmstudio"
    label = "LM Studio (local)"
    is_local = True

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.host = (host or os.getenv("LMSTUDIO_HOST") or "http://localhost:1234").rstrip("/")
        self.model = model or self._first_embed_model() or "text-embedding-nomic-embed-text-v1.5"

    def _first_embed_model(self) -> str | None:
        try:
            data = _http_json(f"{self.host}/v1/models")
        except Exception:  # noqa: BLE001
            return None
        for m in data.get("data", []):
            if "embed" in m.get("id", "").lower():
                return m["id"]
        return None

    def available(self) -> Availability:
        try:
            data = _http_json(f"{self.host}/v1/models")
        except Exception as exc:  # noqa: BLE001
            return Availability(False, f"LM Studio not reachable ({exc})")
        names = [m.get("id", "") for m in data.get("data", []) if "embed" in m.get("id", "").lower()]
        if not names:
            return Availability(False, "No embedding model loaded in LM Studio.")
        return Availability(True, f"LM Studio embeddings at {self.host}", sorted(names))

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = _http_json(
            f"{self.host}/v1/embeddings",
            {"model": self.model, "input": texts},
            timeout=300.0,
        )
        return [d["embedding"] for d in data["data"]]


class OpenAIEmbedder(Embedder):
    key = "openai"
    label = "OpenAI"

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def available(self) -> Availability:
        if not self.api_key:
            return Availability(False, "No OPENAI_API_KEY set.")
        return Availability(
            True, "OpenAI embeddings", ["text-embedding-3-small", "text-embedding-3-large"]
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        resp = client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class HashEmbedder(Embedder):
    """Dependency-free deterministic fallback (hashing trick).

    Not semantically strong, but it keeps semantic chunking and the vector
    retriever *runnable and testable* with zero services and zero network —
    which matters for offline tests and first-run demos.
    """

    key = "hash"
    label = "Hashing (offline fallback)"
    is_local = True

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def available(self) -> Availability:
        return Availability(True, "Offline hashing embedder — always available.")

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import math
        import re

        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


_EMBEDDERS: dict[str, type[Embedder]] = {
    OllamaEmbedder.key: OllamaEmbedder,
    LMStudioEmbedder.key: LMStudioEmbedder,
    OpenAIEmbedder.key: OpenAIEmbedder,
    HashEmbedder.key: HashEmbedder,
}

EMBEDDER_ORDER = ["ollama", "lmstudio", "openai", "hash"]


def build_embedder(key: str, **kwargs) -> Embedder:
    cls = _EMBEDDERS.get((key or "").lower())
    if cls is None:
        raise ValueError(f"Unknown embedder {key!r}. Choose from: {', '.join(EMBEDDER_ORDER)}")
    return cls(**kwargs)


def probe_embedders() -> dict[str, Availability]:
    out: dict[str, Availability] = {}
    for key in EMBEDDER_ORDER:
        try:
            out[key] = _EMBEDDERS[key]().available()
        except Exception as exc:  # noqa: BLE001
            out[key] = Availability(False, f"probe error: {exc}")
    return out


def auto_embedder() -> str:
    """Local-first selection so documents stay on-prem when possible."""
    status = probe_embedders()
    for key in EMBEDDER_ORDER:
        if status.get(key) and status[key].ok:
            return key
    return "hash"
