"""Cached resources and helpers for the Streamlit UI.

Kept separate from ``app.py`` so the caching rules stay obvious: anything
expensive (indexing, network probes) is cached here, while ``app.py`` is
pure layout and event handling.
"""

from __future__ import annotations

import os

import streamlit as st

from factory_knowledge.config import settings
from factory_knowledge.orchestrator import FactoryKnowledge
from factory_knowledge.providers import (
    PROVIDER_ORDER,
    Availability,
    build_provider,
    probe_all,
)
from factory_knowledge.sessions import SessionStore

# Human labels for the provider picker.
PROVIDER_LABELS = {
    "ollama": "Ollama (local)",
    "lmstudio": "LM Studio (local)",
    "openai": "OpenAI (API)",
    "anthropic": "Anthropic (API)",
    "copilot": "GitHub Copilot",
    "none": "Retrieval-only (no LLM)",
}


@st.cache_resource(show_spinner="Indexing official documentation…")
def get_factory(strategy: str, retriever: str) -> FactoryKnowledge:
    """Build and warm up the assistant.

    ``strategy`` and ``retriever`` are part of the cache key on purpose: when
    the user switches chunking strategy or retriever in the sidebar, Streamlit
    rebuilds the index instead of silently serving stale chunks.

    Returns ``(assistant, fallback_message)``. The warning is *returned* rather
    than rendered here on purpose: ``st.cache_resource`` replays any widget
    written inside the function on every cache hit, so calling ``st.warning``
    in here would keep showing a stale ChromaDB warning long after the real
    cause was fixed. The caller decides whether to display it.
    """
    import copy

    cfg = copy.copy(settings)
    cfg.chunk_strategy = strategy
    cfg.retriever = retriever
    try:
        fk = FactoryKnowledge(cfg)
        fallback = ""
    except ImportError as exc:
        # Usually means the app was launched with a different Python than the
        # project venv (bare `streamlit run` picks up the system install).
        # Fall back to the dependency-free keyword retriever so the app works.
        cfg.retriever = "keyword"
        fk = FactoryKnowledge(cfg)
        fallback = (
            f"**Falling back to the `keyword` retriever.** `{retriever}` needs a "
            f"package missing from the Python running this app:\n\n> {exc}\n\n"
            "Launch with `.venv/Scripts/python.exe -m streamlit run app.py` "
            "(or `bash run_app.sh`)."
        )
    for agent in fk.agents.values():
        agent.index(strategy=strategy)
    return fk, fallback


@st.cache_resource(show_spinner=False)
def get_store() -> SessionStore:
    """One SQLite session store per server process."""
    return SessionStore()


@st.cache_data(ttl=60, show_spinner="Checking which models are reachable…")
def get_provider_status() -> dict[str, tuple[bool, str, list[str]]]:
    """Probe every backend. Cached 60s so we don't hammer the endpoints.

    Returns plain tuples rather than ``Availability`` objects because
    ``st.cache_data`` needs picklable, hash-stable values.
    """
    out: dict[str, tuple[bool, str, list[str]]] = {}
    for key, av in probe_all().items():
        out[key] = (av.ok, av.detail, av.models)
    return out


def provider_choices(status: dict[str, tuple[bool, str, list[str]]]) -> list[str]:
    """Provider keys ordered with the usable ones first."""
    usable = [k for k in PROVIDER_ORDER if status.get(k, (False,))[0]]
    rest = [k for k in PROVIDER_ORDER if k not in usable]
    return usable + rest


def make_provider(key: str, model: str | None):
    """Instantiate a provider, tolerating a blank model (use its default)."""
    return build_provider(key, model=model or None)


def apply_provider(fk: FactoryKnowledge, provider) -> None:
    """Point every role agent at the chosen LLM backend."""
    for agent in fk.agents.values():
        agent.provider = provider


def mask_key(key: str) -> str:
    """Show the head and tail of a secret so the user can tell WHICH key is
    loaded without exposing it. Short strings are fully masked."""
    key = (key or "").strip()
    if len(key) <= 12:
        return "•" * len(key)
    return f"{key[:7]}…{key[-4:]}"


def format_status(ok: bool, detail: str) -> str:
    icon = "🟢" if ok else "⚪"
    return f"{icon} {detail}" if detail else icon


# --- Credentials entered through the UI ------------------------------------
_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "copilot": "GITHUB_COPILOT_TOKEN",
}


def set_api_key(provider_key: str, value: str) -> None:
    """Publish a UI-entered key to this process.

    Providers read their credentials from the environment, so setting it here
    makes every later ``build_provider`` call pick it up without restarting.
    Deliberately process-only: nothing is written to disk, so a key typed for a
    demo disappears when the server stops.
    """
    var = _KEY_ENV.get(provider_key)
    if not var:
        return
    if value:
        os.environ[var] = value.strip()
    else:
        os.environ.pop(var, None)


# --- GitHub Copilot device-flow login ---------------------------------------
# The same flow the Copilot CLI and editors use: ask GitHub for a user code,
# the user enters it in a browser, then poll until they approve. No client
# secret is needed, so it is safe to ship in a desktop app.
#
# The client id matters: it must be an app entitled to Copilot, otherwise the
# OAuth token is issued fine but the later token exchange returns 403. This is
# the public VS Code Copilot client id, the same one the editor uses.
_GH_CLIENT_ID = "Iv1.b507a08c87ecfe98"          # public Copilot client id
_GH_SCOPE = "read:user copilot"
_GH_DEVICE_URL = "https://github.com/login/device/code"
_GH_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GH_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Editor-Version": "vscode/1.95.0",
    "User-Agent": "GitHubCopilotChat/0.22.4",
}


def copilot_start_login() -> dict:
    """Step 1: ask GitHub for a device + user code."""
    import json
    import urllib.request

    req = urllib.request.Request(
        _GH_DEVICE_URL,
        data=json.dumps({"client_id": _GH_CLIENT_ID, "scope": _GH_SCOPE}).encode(),
        headers=_GH_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def copilot_poll_login(device_code: str) -> tuple[str | None, str]:
    """Step 2: poll until the user approves. Returns (token, status)."""
    import json
    import urllib.request

    req = urllib.request.Request(
        _GH_TOKEN_URL,
        data=json.dumps({
            "client_id": _GH_CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }).encode(),
        headers=_GH_HEADERS,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except Exception as exc:  # noqa: BLE001
        return None, f"error: {exc}"
    if data.get("access_token"):
        return data["access_token"], "ok"
    return None, data.get("error", "unknown")


# Embedding models appear in Ollama/LM Studio's model list but cannot chat —
# selecting one produces a confusing failure, so hide them from the picker.
_EMBED_HINTS = ("embed", "bge", "gte-", "e5-", "minilm", "nomic-embed")


def chat_models(models: list[str]) -> list[str]:
    """Drop embedding-only models from a provider's model list."""
    usable = [m for m in models if not any(h in m.lower() for h in _EMBED_HINTS)]
    return usable or models  # never leave the picker empty


# --- DBA telemetry (text-to-SQL) -------------------------------------------
# Words that mean "this is a database-telemetry question", which must be
# computed with SQL rather than retrieved with RAG.
_DBA_WORDS = {
    "sql server", "database", "databases", "session", "sessions", "spid",
    "blocking", "blocked", "deadlock", "wait", "waits", "wait type",
    "cpu", "memory", "reads", "writes", "physical read", "query", "queries",
    "db06", "tempdb", "login", "host_name", "program_name", "telemetry",
    "dba", "workload", "sleeping", "suspended", "runnable",
}


def is_dba_question(text: str) -> bool:
    """True when a question is about the DB session workbook, not the manuals."""
    low = text.lower()
    return any(w in low for w in _DBA_WORDS)


@st.cache_resource(show_spinner="Loading session telemetry…")
def get_dba_store():
    """Parse the workbook once per process."""
    from dba.store import get_store as _get

    return _get()


def ask_dba(question: str, provider_key: str, model: str | None):
    """Run one text-to-SQL question, reusing the cached workbook."""
    from dba.agent import DBAAgent, DBAAnswer

    try:
        store = get_dba_store()
    except Exception as exc:  # noqa: BLE001 - surface as an in-chat error
        return DBAAnswer(question, "", error=f"Could not load workbook: {exc}")

    agent = DBAAgent(provider=make_provider(provider_key, model), store=store)
    return agent.ask(question)


__all__ = [
    "Availability",
    "PROVIDER_LABELS",
    "apply_provider",
    "format_status",
    "get_factory",
    "get_provider_status",
    "get_store",
    "make_provider",
    "provider_choices",
]
