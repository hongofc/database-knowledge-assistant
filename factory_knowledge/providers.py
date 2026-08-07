"""Pluggable LLM + embedding providers with live availability detection.

The whole point of this module: the factory floor may run fully air-gapped
(Ollama / LM Studio on a local box) or fall back to a hosted API when local
inference is too slow. Rather than hard-coding one path, every provider
implements the same tiny contract and advertises whether it is *actually
reachable right now* — so the UI can show "connected to X" and let the user
switch on the fly.

Contract
--------
``LLMProvider.chat(messages) -> str``          synthesize an answer
``LLMProvider.available() -> Availability``    is it usable this second?
``LLMProvider.models() -> list[str]``          what can we pick?

Adding a provider = subclass + register in ``_REGISTRY``. Nothing else changes.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

# Short timeout: availability probes must never hang the UI.
_PROBE_TIMEOUT = 2.0
_CHAT_TIMEOUT = 120.0


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMError(RuntimeError):
    """Raised when a configured provider fails to answer."""


@dataclass
class Availability:
    """Result of probing a provider."""

    ok: bool
    detail: str = ""
    models: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # lets callers write `if avail:`
        return self.ok


def _http_json(url: str, payload: dict | None = None, headers: dict | None = None,
               timeout: float = _PROBE_TIMEOUT) -> dict:
    """Minimal JSON HTTP helper (stdlib only — no extra dependency)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class LLMProvider:
    """Common interface for every chat backend."""

    key: str = "base"
    label: str = "Base"
    is_local: bool = False

    def __init__(self, model: str | None = None, temperature: float = 0.1) -> None:
        self.model = model
        self.temperature = temperature

    def available(self) -> Availability:
        raise NotImplementedError

    def chat(self, messages: list[Message]) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{type(self).__name__} model={self.model!r}>"


# ---------------------------------------------------------------------------
# Local providers — OpenAI-compatible /v1 servers
# ---------------------------------------------------------------------------
_EMBEDDING_HINTS = ("embed", "embedding", "bge-", "gte-", "e5-", "minilm")


def _is_embedding_model(name: str) -> bool:
    """Embedding models appear in local model lists but cannot chat; sending
    them to /v1/chat/completions returns HTTP 400."""
    low = name.lower()
    return any(h in low for h in _EMBEDDING_HINTS)


class OllamaProvider(LLMProvider):
    """Ollama. Native API for tags, OpenAI-compatible /v1 for chat."""

    key = "ollama"
    label = "Ollama (local)"
    is_local = True
    default_host = "http://localhost:11434"

    def __init__(self, model: str | None = None, temperature: float = 0.1,
                 host: str | None = None) -> None:
        super().__init__(model, temperature)
        self.host = (host or os.getenv("OLLAMA_HOST") or self.default_host).rstrip("/")

    def available(self) -> Availability:
        try:
            data = _http_json(f"{self.host}/api/tags")
        except Exception as exc:  # noqa: BLE001 - any failure means "not usable"
            return Availability(False, f"Ollama not reachable at {self.host} ({exc})")
        names = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        if not names:
            return Availability(
                False,
                f"Ollama is running at {self.host} but has no models. "
                "Pull one, e.g. `ollama pull qwen2.5:3b`.",
            )
        return Availability(True, f"Ollama at {self.host}", sorted(names))

    def chat(self, messages: list[Message]) -> str:
        # Pick a CHAT model when none was specified. The naive choice —
        # models[0] of a sorted list — lands on "nomic-embed-text", an
        # embedding model that cannot chat, so Ollama returns HTTP 400.
        model = self.model
        if not model:
            names = self.available().models or []
            usable = [n for n in names if not _is_embedding_model(n)]
            model = (usable or names or ["qwen2.5:3b"])[0]
        try:
            data = _http_json(
                f"{self.host}/v1/chat/completions",
                {
                    "model": model,
                    "temperature": self.temperature,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                },
                timeout=_CHAT_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Ollama request failed: {exc}") from exc
        return (data["choices"][0]["message"]["content"] or "").strip()


class LMStudioProvider(LLMProvider):
    """LM Studio's local server is OpenAI-compatible on port 1234 by default."""

    key = "lmstudio"
    label = "LM Studio (local)"
    is_local = True
    default_host = "http://localhost:1234"

    def __init__(self, model: str | None = None, temperature: float = 0.1,
                 host: str | None = None) -> None:
        super().__init__(model, temperature)
        self.host = (host or os.getenv("LMSTUDIO_HOST") or self.default_host).rstrip("/")

    def available(self) -> Availability:
        try:
            data = _http_json(f"{self.host}/v1/models")
        except Exception as exc:  # noqa: BLE001
            return Availability(
                False,
                f"LM Studio not reachable at {self.host} — start its local server ({exc})",
            )
        names = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        if not names:
            return Availability(False, "LM Studio is up but no model is loaded.")
        return Availability(True, f"LM Studio at {self.host}", sorted(names))

    def chat(self, messages: list[Message]) -> str:
        model = self.model or (self.available().models or ["local-model"])[0]
        try:
            data = _http_json(
                f"{self.host}/v1/chat/completions",
                {
                    "model": model,
                    "temperature": self.temperature,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                },
                timeout=_CHAT_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"LM Studio request failed: {exc}") from exc
        return (data["choices"][0]["message"]["content"] or "").strip()


# ---------------------------------------------------------------------------
# Hosted providers
# ---------------------------------------------------------------------------
class OpenAIProvider(LLMProvider):
    key = "openai"
    label = "OpenAI"
    default_model = "gpt-4o-mini"

    def __init__(self, model: str | None = None, temperature: float = 0.1,
                 api_key: str | None = None) -> None:
        super().__init__(model or self.default_model, temperature)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def available(self) -> Availability:
        if not self.api_key:
            return Availability(False, "No OPENAI_API_KEY set.")
        # Ask the API which models this key can actually use, rather than
        # trusting a hardcoded list that silently goes stale as OpenAI adds
        # and retires models. This also validates the key for real: a bad key
        # fails here instead of at the first question.
        try:
            data = _http_json(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except Exception as exc:  # noqa: BLE001
            return Availability(False, f"OpenAI key rejected: {exc}")
        ids = [m.get("id", "") for m in data.get("data", [])]
        # Keep chat models only: the same list carries embeddings, whisper,
        # tts, dall-e and moderation models, none of which can answer a chat
        # request (selecting one would fail at question time).
        chat = sorted(
            m for m in ids
            if m.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-"))
            and not any(x in m for x in
                        ("embed", "tts", "whisper", "audio", "realtime",
                         "image", "moderation", "transcribe", "search"))
        )
        return Availability(
            True,
            f"OpenAI key valid — {len(chat)} chat models",
            chat or ["gpt-4o-mini"],
        )

    def chat(self, messages: list[Message]) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("pip install openai") from exc
        client = OpenAI(api_key=self.api_key)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"OpenAI request failed: {exc}") from exc
        return (resp.choices[0].message.content or "").strip()


class AnthropicProvider(LLMProvider):
    key = "anthropic"
    label = "Anthropic (Claude)"
    default_model = "claude-3-5-haiku-20241022"

    def __init__(self, model: str | None = None, temperature: float = 0.1,
                 api_key: str | None = None) -> None:
        super().__init__(model or self.default_model, temperature)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    def available(self) -> Availability:
        if not self.api_key:
            return Availability(False, "No ANTHROPIC_API_KEY set.")
        # Anthropic exposes /v1/models too, so the same rule applies: fetch the
        # live list instead of hardcoding names that get retired.
        try:
            data = _http_json(
                "https://api.anthropic.com/v1/models?limit=100",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return Availability(False, f"Anthropic key rejected: {exc}")
        ids = sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))
        return Availability(
            True,
            f"Anthropic key valid — {len(ids)} models",
            ids or [self.default_model],
        )

    def chat(self, messages: list[Message]) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("pip install anthropic") from exc
        client = anthropic.Anthropic(api_key=self.api_key)
        # Claude takes the system prompt as a top-level arg, not a message.
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        convo = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=self.temperature,
                system=system or None,
                messages=convo,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


class CopilotProvider(LLMProvider):
    """GitHub Copilot via its OpenAI-compatible endpoint.

    Uses an OAuth token from the environment or from the GitHub Copilot CLI /
    editor config on disk, exchanged for a short-lived API token.
    """

    key = "copilot"
    label = "GitHub Copilot"
    default_model = "gpt-4o-mini"
    _API = "https://api.githubcopilot.com"
    _TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"

    def __init__(self, model: str | None = None, temperature: float = 0.1,
                 oauth_token: str | None = None) -> None:
        super().__init__(model or self.default_model, temperature)
        self.oauth_token = oauth_token or self._find_oauth_token()

    @staticmethod
    def _find_oauth_token() -> str | None:
        """Look for a Copilot OAuth token in env, then editor config files."""
        for var in ("GITHUB_COPILOT_TOKEN", "COPILOT_OAUTH_TOKEN", "GH_COPILOT_TOKEN"):
            if os.getenv(var):
                return os.getenv(var)
        candidates = [
            os.path.expanduser("~/AppData/Local/github-copilot/apps.json"),
            os.path.expanduser("~/AppData/Local/github-copilot/hosts.json"),
            os.path.expanduser("~/.config/github-copilot/apps.json"),
            os.path.expanduser("~/.config/github-copilot/hosts.json"),
        ]
        for path in candidates:
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:  # noqa: BLE001 - file absent or malformed
                continue
            for value in data.values():
                if isinstance(value, dict) and value.get("oauth_token"):
                    return value["oauth_token"]
        return None

    def _api_token(self) -> str:
        # GitHub's Copilot token endpoint returns 403 unless the request looks
        # like it came from a real editor: the editor/plugin version and a
        # matching User-Agent are required, not just the OAuth token.
        data = _http_json(
            self._TOKEN_URL,
            headers={
                "Authorization": f"token {self.oauth_token}",
                "Accept": "application/json",
                "Editor-Version": "vscode/1.95.0",
                "Editor-Plugin-Version": "copilot-chat/0.22.4",
                "User-Agent": "GitHubCopilotChat/0.22.4",
            },
        )
        token = data.get("token")
        if not token:
            raise LLMError("Copilot token exchange returned no token.")
        return token

    # Headers GitHub expects on every Copilot API call. Without the editor
    # identification the endpoints return 400/403 even with a valid token.
    _EDITOR_HEADERS = {
        "Editor-Version": "vscode/1.95.0",
        "Editor-Plugin-Version": "copilot-chat/0.22.4",
        "Copilot-Integration-Id": "vscode-chat",
        "User-Agent": "GitHubCopilotChat/0.22.4",
    }

    def _models(self, api_token: str) -> list[str]:
        """Ask Copilot which models this account may actually use.

        The entitled list is per-account: an org admin decides what is enabled,
        so hardcoding names guarantees drift. Falls back to a minimal safe list
        only if the endpoint is unavailable.
        """
        try:
            data = _http_json(
                f"{self._API}/models",
                headers={"Authorization": f"Bearer {api_token}", **self._EDITOR_HEADERS},
            )
        except Exception:  # noqa: BLE001 - fall back below
            return ["gpt-4o-mini"]
        out: list[str] = []
        for item in data.get("data", []):
            mid = item.get("id")
            if not mid:
                continue
            # Only chat-capable models; embeddings appear here too.
            caps = item.get("capabilities", {})
            if caps.get("type") and caps["type"] != "chat":
                continue
            out.append(mid)
        return out or ["gpt-4o-mini"]

    def available(self) -> Availability:
        if not self.oauth_token:
            return Availability(
                False,
                "No Copilot OAuth token found. Sign in via the GitHub Copilot "
                "CLI/editor, or set GITHUB_COPILOT_TOKEN.",
            )
        try:
            api_token = self._api_token()
        except Exception as exc:  # noqa: BLE001
            return Availability(False, f"Copilot token exchange failed: {exc}")
        return Availability(
            True,
            "GitHub Copilot authenticated",
            self._models(api_token),
        )

    def chat(self, messages: list[Message]) -> str:
        try:
            data = _http_json(
                f"{self._API}/chat/completions",
                {
                    "model": self.model,
                    "temperature": self.temperature,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                },
                headers={
                    "Authorization": f"Bearer {self._api_token()}",
                    **self._EDITOR_HEADERS,
                },
                timeout=_CHAT_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Copilot request failed: {exc}") from exc
        return (data["choices"][0]["message"]["content"] or "").strip()


class RetrievalOnlyProvider(LLMProvider):
    """Always-available fallback: stitch an answer from retrieved context.

    Guarantees the demo never hard-fails, even with no key and no local model.
    """

    key = "none"
    label = "Retrieval only (no LLM)"
    is_local = True

    def available(self) -> Availability:
        return Availability(True, "Always available — extractive answers, no synthesis.")

    def chat(self, messages: list[Message]) -> str:
        user_msgs = [m.content for m in messages if m.role == "user"]
        last = user_msgs[-1] if user_msgs else ""
        context = ""
        if "Context:" in last:
            context = last.split("Context:", 1)[1].split("Question:", 1)[0].strip()
        if not context:
            return (
                "[retrieval-only mode] Nothing relevant found in the official "
                "documentation, and no language model is configured."
            )
        return (
            "[retrieval-only mode] Based on the most relevant official documentation:\n\n"
            f"{context}"
        )


_REGISTRY: dict[str, type[LLMProvider]] = {
    OllamaProvider.key: OllamaProvider,
    LMStudioProvider.key: LMStudioProvider,
    OpenAIProvider.key: OpenAIProvider,
    AnthropicProvider.key: AnthropicProvider,
    CopilotProvider.key: CopilotProvider,
    RetrievalOnlyProvider.key: RetrievalOnlyProvider,
}

PROVIDER_ORDER = ["ollama", "lmstudio", "openai", "anthropic", "copilot", "none"]


def build_provider(key: str, **kwargs) -> LLMProvider:
    """Factory: provider key -> configured instance."""
    cls = _REGISTRY.get((key or "").lower())
    if cls is None:
        raise LLMError(
            f"Unknown provider {key!r}. Choose from: {', '.join(PROVIDER_ORDER)}"
        )
    return cls(**kwargs)


def probe_all() -> dict[str, Availability]:
    """Probe every provider so the UI can render a live status board."""
    out: dict[str, Availability] = {}
    for key in PROVIDER_ORDER:
        try:
            out[key] = _REGISTRY[key]().available()
        except Exception as exc:  # noqa: BLE001 - a broken probe must not crash the UI
            out[key] = Availability(False, f"probe error: {exc}")
    return out


def auto_select(prefer_local: bool = True) -> str:
    """Pick the best usable provider: local first (private, free), then hosted."""
    status = probe_all()
    order = PROVIDER_ORDER if prefer_local else [
        k for k in PROVIDER_ORDER if not _REGISTRY[k]().is_local
    ] + PROVIDER_ORDER
    for key in order:
        if key != "none" and status.get(key) and status[key].ok:
            return key
    return "none"
