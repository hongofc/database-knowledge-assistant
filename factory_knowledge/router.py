"""Decide which specialist should handle a question.

Two strategies ship in the box, both behind :func:`route`:

* ``keyword`` (default) — score each role by how many of its keywords appear
  in the question. Fast, free, no LLM.
* ``llm`` — ask the language model to classify the question into a role. More
  robust for fuzzy questions; costs one extra (small) LLM call.

Select with ``ROUTER=keyword`` or ``ROUTER=llm`` in your ``.env``.
"""

from __future__ import annotations

from .config import Settings, settings
from .llm import Message, chat
from .rag.keyword_retriever import tokenize
from .roles import RoleConfig


def route(question: str, roles: list[RoleConfig], cfg: Settings | None = None) -> RoleConfig:
    """Return the best-matching role for ``question``."""
    cfg = cfg or settings
    if not roles:
        raise ValueError("No roles configured.")
    if len(roles) == 1:
        return roles[0]

    if cfg.router == "llm" and cfg.llm_enabled:
        chosen = _llm_route(question, roles, cfg)
        if chosen is not None:
            return chosen
        # Fall through to keyword routing if the LLM gave an unusable answer.

    return _keyword_route(question, roles)


def _keyword_route(question: str, roles: list[RoleConfig]) -> RoleConfig:
    q_tokens = set(tokenize(question))
    q_lower = question.lower()
    best, best_score = roles[0], -1.0
    for role in roles:
        score = 0.0
        for kw in role.keywords:
            # Multi-word keywords (e.g. "first aid") matched as substrings.
            if " " in kw:
                if kw in q_lower:
                    score += 2.0
            elif kw in q_tokens:
                score += 1.0
        if score > best_score:
            best, best_score = role, score
    return best


def _llm_route(question: str, roles: list[RoleConfig], cfg: Settings) -> RoleConfig | None:
    menu = "\n".join(f"- {r.key}: {r.description}" for r in roles)
    system = (
        "You are a router that assigns a factory-floor question to exactly one "
        "specialist. Reply with ONLY the specialist's key, nothing else."
    )
    user = f"Specialists:\n{menu}\n\nQuestion: {question}\n\nKey:"
    reply = chat([Message("system", system), Message("user", user)], cfg).strip().lower()
    by_key = {r.key: r for r in roles}
    for key, role in by_key.items():
        if key in reply.split() or reply == key:
            return role
    return None
