"""LLM provider abstraction.

The rest of the kit only ever calls :func:`chat`. That keeps the door open to
swapping OpenAI for Gemini, a local Ollama model, or anything else later —
just add a branch here. If no provider is configured, we fall back to a
deterministic "extractive" answer built from the retrieved context, so the
whole pipeline still runs (and demos) without any API spend.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, settings
# Single Message type shared by the legacy llm.chat() path and the new
# pluggable providers, so an agent can hand the same list to either.
from .providers import Message


@dataclass
class Message_Legacy:  # pragma: no cover - retained for backwards compatibility
    role: str
    content: str


class LLMError(RuntimeError):
    """Raised when a configured provider fails to answer."""


def chat(messages: list[Message], cfg: Settings | None = None) -> str:
    """Return the assistant's reply for a list of chat messages.

    Dispatches on ``cfg.llm_provider``. Add new providers by extending the
    dispatch table below — the calling code never changes.
    """
    cfg = cfg or settings

    if not cfg.llm_enabled:
        return _fallback_answer(messages)

    if cfg.llm_provider == "openai":
        return _openai_chat(messages, cfg)

    # UPGRADE POINT: add elif branches for "gemini", "ollama", "anthropic"...
    raise LLMError(f"Unknown LLM provider: {cfg.llm_provider!r}")


def _openai_chat(messages: list[Message], cfg: Settings) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - import guard
        raise LLMError(
            "The 'openai' package is not installed. Run: pip install openai"
        ) from exc

    client = OpenAI(api_key=cfg.openai_api_key)
    try:
        resp = client.chat.completions.create(
            model=cfg.chat_model,
            temperature=cfg.temperature,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
    except Exception as exc:  # noqa: BLE001 - surface any SDK/network error clearly
        raise LLMError(f"OpenAI request failed: {exc}") from exc
    return (resp.choices[0].message.content or "").strip()


def _fallback_answer(messages: list[Message]) -> str:
    """No-LLM mode: stitch a readable answer from the supplied context.

    This is intentionally simple. It lets students see retrieval working
    end-to-end before they add an API key. The context is injected by the
    agent as the latest user message, after a ``Context:`` marker.
    """
    user_msgs = [m.content for m in messages if m.role == "user"]
    last = user_msgs[-1] if user_msgs else ""
    context = ""
    if "Context:" in last:
        context = last.split("Context:", 1)[1]
        context = context.split("Question:", 1)[0].strip()

    if not context:
        return (
            "[no-LLM mode] I could not find relevant information in the official "
            "documentation, and no language model is configured. Add your "
            "OPENAI_API_KEY to .env to enable full answers."
        )
    return (
        "[no-LLM mode] Based on the most relevant official documentation I found:\n\n"
        f"{context}\n\n"
        "(Add OPENAI_API_KEY to .env for a synthesized, conversational answer.)"
    )
