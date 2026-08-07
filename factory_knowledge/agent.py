"""A single specialist agent: RAG + persona + hallucination guardrail.

When asked a question the agent (1) retrieves relevant chunks from its role's
official documents, (2) **abstains** if nothing relevant is found (so it never
invents an answer), otherwise (3) builds a grounded, citation-instructed prompt
and asks the LLM to answer using only that context.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, settings
from .ingest import build_chunks
from .llm import Message, chat
from .rag.base import Chunk, build_retriever
from .roles import RoleConfig


@dataclass
class Answer:
    """An agent's reply plus the evidence it used (for verifiable citations)."""

    text: str
    role_name: str
    sources: list[Chunk]
    grounded: bool = True  # False when the agent abstained (no supporting docs)

    def cited_sources(self) -> list[str]:
        """De-duplicated, human-readable citations (source > section / page)."""
        seen, out = set(), []
        for c in self.sources:
            cite = c.citation()
            if cite not in seen:
                seen.add(cite)
                out.append(cite)
        return out


class RoleAgent:
    """Wraps one :class:`RoleConfig` with its own retriever and prompt."""

    def __init__(self, role: RoleConfig, cfg: Settings | None = None,
                 provider=None) -> None:
        self.role = role
        self.cfg = cfg or settings
        # Each role needs its OWN vector collection. Without a unique name every
        # agent would create and then delete the same Chroma collection, wiping
        # the previously-indexed specialist (only the last one would survive).
        kwargs: dict = {}
        if self.cfg.retriever in ("vector", "hybrid"):
            kwargs["collection_name"] = f"factory_knowledge_{role.key}"
        self.retriever = build_retriever(self.cfg.retriever, **kwargs)
        self.provider = provider  # runtime LLM override (set by the UI switcher)
        self._indexed = False

    # -- lifecycle ----------------------------------------------------------
    def index(self, strategy: str | None = None) -> int:
        """Load this role's documents and build its searchable index.

        Returns the number of chunks indexed (handy for diagnostics).
        """
        chunks = build_chunks(self.role.data_dir, self.role.key, strategy=strategy)
        self.retriever.index(chunks)
        self._indexed = True
        return len(chunks)

    # -- answering ----------------------------------------------------------
    def answer(self, question: str, history: list[dict] | None = None) -> Answer:
        """Answer ``question``, optionally continuing a prior conversation.

        ``history`` is a list of ``{"role","content"}`` turns from the session
        store, so follow-ups like "and what's the next step?" resolve correctly.
        """
        if not self._indexed:
            self.index()

        hits = self.retriever.retrieve(question, top_k=self.cfg.top_k)

        # Hallucination guardrail: keep only chunks above the trust floor, and
        # abstain entirely if nothing relevant remains. This is deterministic —
        # it happens before any LLM call, so the model can't invent an answer.
        trusted = [h for h in hits if h.score >= self.cfg.min_score]
        if not trusted:
            return Answer(
                text=self._abstain_message(),
                role_name=self.role.name,
                sources=[],
                grounded=False,
            )

        context = self._format_context(trusted)
        messages = [Message(role="system", content=self.role.system_prompt)]
        for turn in (history or [])[-6:]:
            messages.append(Message(role=turn["role"], content=turn["content"]))
        messages.append(
            Message(role="user", content=self._build_user_prompt(question, context))
        )

        # A runtime provider (chosen in the UI) wins over the .env default.
        if self.provider is not None:
            reply = self.provider.chat(messages)
        else:
            reply = chat(messages, self.cfg)
        return Answer(text=reply, role_name=self.role.name, sources=trusted, grounded=True)

    # -- prompt construction ------------------------------------------------
    def _abstain_message(self) -> str:
        return (
            f"I could not find this in the official {self.role.name} documentation, "
            "so I won't guess. Please rephrase with the equipment or procedure name, "
            "or escalate to your supervisor / the relevant engineer for guidance."
        )

    @staticmethod
    def _format_context(hits: list[Chunk]) -> str:
        blocks = []
        for i, c in enumerate(hits, 1):
            blocks.append(f"[{i}] (source: {c.citation()})\n{c.text}")
        return "\n\n".join(blocks)

    @staticmethod
    def _build_user_prompt(question: str, context: str) -> str:
        # The "Context:" / "Question:" markers are also what the no-LLM fallback
        # in llm.py looks for, so keep them in sync if you edit this.
        return (
            "Answer the question using ONLY the official documentation below. Cite "
            "the [number] of every source you rely on. If the answer is not fully "
            "supported by the context, say it is not in the official documentation "
            "and recommend escalation — do not guess.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )
