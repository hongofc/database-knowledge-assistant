"""Factory Knowledge Assistant — a grounded RAG + text-to-SQL assistant for the factory floor.

Capstone Level 2 starter. A Retrieval-Augmented Generation (RAG) system that
answers technicians' questions from *official floor documentation* — equipment
manuals, safety SOPs, and maintenance logs — with **verifiable citations** and a
**hallucination guardrail** that abstains when the answer isn't in the docs.

It ships with three specialist assistants — Maintenance & Troubleshooting,
Safety & Compliance, and Quality & Operations — but the design is the same small,
swappable template used by the Office Navigator kit:

1. Runs locally and cheaply. The default retriever is pure-Python (no heavy
   dependencies) and the LLM layer degrades gracefully without an API key.
2. Simple first, enterprise later. Every moving part (retriever, LLM, router)
   sits behind a small interface, so the toy BM25 retriever can be swapped for a
   production vector database without touching the rest of the code.
3. Extensible by configuration. Add a specialist (e.g. "Electrical", "Robotics")
   by editing ``roles.yaml`` and dropping documents in a folder — no new Python.
"""

from .orchestrator import FactoryKnowledge

__all__ = ["FactoryKnowledge"]
__version__ = "0.1.0"
