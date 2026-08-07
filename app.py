"""Streamlit web UI for the Factory Knowledge assistant.

Run it::

    .venv/Scripts/python.exe -m streamlit run app.py

Gives technicians a chat interface with:
  * a **provider switcher** (local Ollama / LM Studio, or hosted APIs)
  * **persistent sessions** — past conversations resume after a restart
  * **citations** for every answer, and a visible abstain flag
  * a **RAG settings** panel to compare chunking strategies live
"""

from __future__ import annotations

import os

import streamlit as st

from factory_knowledge.chunking import available_strategies
from factory_knowledge.config import settings
from factory_knowledge.providers import LLMError
from ui_helpers import (
    PROVIDER_LABELS,
    apply_provider,
    ask_dba,
    chat_models,
    copilot_poll_login,
    copilot_start_login,
    format_status,
    get_factory,
    get_provider_status,
    get_store,
    is_dba_question,
    make_provider,
    mask_key,
    provider_choices,
    set_api_key,
)


def render_copilot_login(ok: bool) -> None:
    """GitHub device-flow sign-in, the same pattern OpenCode and the Copilot
    CLI use: show a code, the user approves it in a browser, we poll."""
    if ok:
        st.success("Signed in to GitHub Copilot.")
        return

    flow = st.session_state.get("copilot_flow")
    if not flow:
        st.caption("Not signed in.")
        if st.button("🔗 Sign in with GitHub", use_container_width=True):
            try:
                st.session_state.copilot_flow = copilot_start_login()
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not start GitHub login: {exc}")
        st.caption("Or paste a token below.")
        token = st.text_input("Copilot OAuth token", type="password",
                              placeholder="gho_… (or set GITHUB_COPILOT_TOKEN)")
        if token:
            set_api_key("copilot", token)
            get_provider_status.clear()
            st.rerun()
        return

    # A login is in progress: show the code and let the user confirm.
    st.info(
        f"1. Open **{flow.get('verification_uri')}**\n\n"
        f"2. Enter this code:\n\n### `{flow.get('user_code')}`"
    )
    st.link_button("Open GitHub", flow.get("verification_uri", "https://github.com/login/device"),
                   use_container_width=True)
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ I've approved", use_container_width=True):
            token, statustxt = copilot_poll_login(flow.get("device_code", ""))
            if token:
                set_api_key("copilot", token)
                st.session_state.pop("copilot_flow", None)
                # Select Copilot now that it works, instead of leaving the user
                # on whatever provider they had before signing in.
                st.session_state.provider_key = "copilot"
                st.session_state.pop("provider_select", None)
                get_provider_status.clear()
                st.rerun()
            elif statustxt == "authorization_pending":
                st.warning("Not approved yet — finish in the browser, then click again.")
            else:
                st.error(f"Login failed: {statustxt}")
    with col_b:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("copilot_flow", None)
            st.rerun()


def render_sidebar(store):
    """Sidebar: sessions, provider switching, RAG settings. Returns UI state."""
    with st.sidebar:
        try:
            # Full wordmark in the sidebar: it's a wide space, so the 1550x171
            # transparent PNG reads perfectly here. The browser tab uses the
            # square icon.png instead — a 9:1 banner squeezed into a 32x32
            # favicon renders only 3px tall and is unreadable.
            # The M is the limiting detail in this wordmark: its thinnest
            # feature is ~24px wide in a 171px-tall source, so at small display
            # sizes it shrinks below ~4px and antialiasing rounds the corners.
            # Measured: 24px tall -> 3.4px stroke (rounded), 33px tall -> 4.6px
            # (square). 300px wide is the smallest size where the M stays sharp.
            # Regenerate with scripts/make_logo.py if you change this width.
            st.image("logo_sidebar.png", width=300)
        except Exception:  # noqa: BLE001 - logo is cosmetic
            pass

        # -- Conversations --------------------------------------------------
        st.header("💬 Conversations")
        if st.button("➕ New chat", use_container_width=True):
            st.session_state.session_id = store.create_session()
            st.rerun()

        sessions = store.list_sessions(limit=25)
        if sessions:
            ids = [s.id for s in sessions]
            labels = {s.id: f"{s.title[:34]}  ·  {s.message_count}" for s in sessions}
            current = st.session_state.get("session_id")
            index = ids.index(current) if current in ids else 0
            picked = st.radio(
                "Resume", ids, index=index,
                format_func=lambda i: labels[i], label_visibility="collapsed",
            )
            if picked != st.session_state.get("session_id"):
                st.session_state.session_id = picked
                st.rerun()

            col_del, col_all = st.columns(2)
            with col_del:
                if st.button("🗑 Delete", use_container_width=True,
                             help="Delete the selected conversation"):
                    store.delete_session(st.session_state.session_id)
                    # Reuse an existing empty chat instead of creating another
                    # one, otherwise deleting always leaves a fresh "New chat"
                    # behind and the list never actually shrinks.
                    remaining = [s for s in store.list_sessions(limit=25)
                                 if s.id != st.session_state.session_id]
                    empty = next((s for s in remaining if s.message_count == 0), None)
                    st.session_state.session_id = (
                        empty.id if empty
                        else (remaining[0].id if remaining else store.create_session())
                    )
                    st.rerun()
            with col_all:
                if st.button("🧹 Clear all", use_container_width=True,
                             help="Delete every conversation"):
                    for s in store.list_sessions(limit=1000):
                        store.delete_session(s.id)
                    st.session_state.session_id = store.create_session()
                    st.rerun()

        st.divider()

        # -- Model ----------------------------------------------------------
        st.header("🧠 Model")
        status = get_provider_status()
        keys = provider_choices(status)
        # A stable key + explicit index is required here. provider_choices()
        # reorders the list as availability changes (signing in to Copilot
        # promotes it), and without this the selectbox would snap back to
        # index 0 — bouncing the user to Ollama right after they logged in.
        remembered = st.session_state.get("provider_key")
        index = keys.index(remembered) if remembered in keys else 0
        provider_key = st.selectbox(
            "Provider", keys, index=index, key="provider_select",
            format_func=lambda k: PROVIDER_LABELS.get(k, k),
            help="Local providers keep factory documents on-premises.",
        )
        st.session_state.provider_key = provider_key
        ok, detail, models = status.get(provider_key, (False, "not probed", []))
        st.caption(format_status(ok, detail))

        # -- Credentials, entered in the UI ---------------------------------
        # Keys typed here live in this browser session only: they are never
        # written to disk and never stored in the chat database.
        if provider_key in ("openai", "anthropic"):
            env_var = "OPENAI_API_KEY" if provider_key == "openai" else "ANTHROPIC_API_KEY"
            # Seed the box from the environment/.env the first time, so a key
            # loaded at startup is visible and replaceable instead of being an
            # invisible background value the user cannot see or override.
            state_key = f"key_{provider_key}"
            if state_key not in st.session_state:
                st.session_state[state_key] = os.getenv(env_var, "")
            saved = st.session_state[state_key]

            with st.expander(
                f"🔑 API key — {'set' if saved else 'not set'}", expanded=not saved
            ):
                if saved:
                    # Show enough to identify WHICH key is in use without
                    # printing the secret in full.
                    st.caption(f"Currently using `{mask_key(saved)}`")
                entered = st.text_input(
                    f"{PROVIDER_LABELS[provider_key]} key", value=saved, type="password",
                    placeholder=f"sk-… (or set {env_var})",
                    help="Kept in this browser session only — never written to disk. "
                         "Click the eye icon to reveal, or paste a new key to replace.",
                    key=f"keyinput_{provider_key}",
                )
                if entered != saved:
                    st.session_state[state_key] = entered
                    set_api_key(provider_key, entered)
                    get_provider_status.clear()   # re-probe with the new key
                    st.rerun()
                if not ok and not entered:
                    st.info(f"Paste a key above, or set `{env_var}` before launching.")

        elif provider_key == "copilot":
            render_copilot_login(ok)

        elif not ok:
            st.warning("Not reachable — answers will fail until it is running.")

        usable = chat_models(models)
        # Key includes the provider so switching providers doesn't carry a
        # stale model name across (each provider has its own model names).
        model = st.selectbox(
            "Model", usable, key=f"model_{provider_key}"
        ) if usable else st.text_input(
            "Model", value="", placeholder="provider default",
            key=f"model_txt_{provider_key}",
        )

        st.divider()

        # -- RAG settings ---------------------------------------------------
        st.header("🔍 Retrieval")
        strategies = list(available_strategies())
        strategy = st.selectbox(
            "Chunking strategy", strategies,
            index=strategies.index(settings.chunk_strategy)
            if settings.chunk_strategy in strategies else 0,
            help="HOW documents are cut into pieces before indexing. "
                 "Changing this re-indexes the corpus (~90s).",
        )
        retriever = st.selectbox(
            "Retriever", ["keyword", "vector", "hybrid"],
            index=["keyword", "vector", "hybrid"].index(settings.retriever)
            if settings.retriever in ("keyword", "vector", "hybrid") else 0,
            help="HOW those pieces are searched at question time.",
        )
        st.caption(f"Abstain floor: `{settings.min_score}` (scaled to retriever)")

        with st.expander("ℹ️ What's the difference?"):
            st.markdown(
                "They are two different stages of the same pipeline:\n\n"
                "**Chunking = how documents are cut up** (happens once, at "
                "indexing).\n"
                "- `fixed` — every N characters. Simple control; can slice a "
                "sentence in half.\n"
                "- `recursive` — split on paragraphs, then sentences.\n"
                "- `semantic` — split where the topic changes (slowest).\n"
                "- `metadata_aware` — respects markdown headings and keeps the "
                "heading with its text. **Best here (MRR 0.93).**\n\n"
                "**Retriever = how chunks are found** (happens per question).\n"
                "- `keyword` (BM25) — word overlap. Nails exact codes like "
                "`E-204`; misses paraphrases.\n"
                "- `vector` — embedding similarity. Understands meaning, so "
                "\"what safety gear?\" finds a PPE doc. **Best here.**\n"
                "- `hybrid` — both, fused with RRF. Theoretically strongest, "
                "but measured *worse* on this corpus (0.88 vs 0.93).\n\n"
                "Analogy: chunking decides **how the book is cut into pages**; "
                "the retriever decides **how you find the right page**."
            )

    return provider_key, model, strategy, retriever


def attribution(provider_key: str, model: str, *extra: str) -> str:
    """One consistent 'who answered this' line.

    Shown on every assistant turn — success AND failure — so an error is always
    traceable to a specific provider+model. Without the model name, "Copilot
    failed" is ambiguous: the usual cause is one model the account isn't
    entitled to, not the provider being down.
    """
    label = PROVIDER_LABELS.get(provider_key, provider_key)
    parts = [f"`{label}`", f"`{model or 'default'}`", *(f"`{e}`" for e in extra)]
    return "  ·  ".join(parts)


def render_history(store, session_id):
    """Replay a stored conversation, citations included."""
    for msg in store.get_messages(session_id):
        with st.chat_message(msg.role):
            st.markdown(msg.content)
            if msg.citations:
                with st.expander(f"📚 {len(msg.citations)} citations"):
                    for c in msg.citations:
                        st.write(f"- {c}")
            # Replay the same attribution on stored turns, so scrolling back
            # still shows which model produced (or failed) each answer.
            meta = msg.meta or {}
            if msg.role == "assistant" and meta.get("provider"):
                st.caption(attribution(
                    meta["provider"], meta.get("model", ""),
                    *[v for k, v in meta.items()
                      if k in ("mode", "strategy", "retriever") and v],
                ))


def main() -> None:
    st.set_page_config(page_title="Database Knowledge Assistant",
                       page_icon="icon.png", layout="wide")

    store = get_store()
    if "session_id" not in st.session_state:
        recent = store.list_sessions(limit=1)
        st.session_state.session_id = (
            recent[0].id if recent else store.create_session()
        )
    session_id = st.session_state.session_id

    provider_key, model, strategy, retriever = render_sidebar(store)

    # Tight ratio so the icon sits next to the title instead of being stranded
    # by a wide empty column. vertical_alignment centres the icon against the
    # heading rather than letting it float to the top.
    head_l, head_r = st.columns([1, 11], vertical_alignment="center")
    with head_l:
        try:
            st.image("icon.png", width=64)
        except Exception:  # noqa: BLE001 - logo is cosmetic
            pass
    with head_r:
        st.title("Database Knowledge Assistant")
        st.caption(
            "Grounded answers about SQL Server sessions and workload telemetry — "
            "every number computed with SQL you can re-run, and an explicit "
            "refusal when the data doesn't cover it."
        )

    fk, fallback_msg = get_factory(strategy, retriever)
    if fallback_msg:
        st.warning(fallback_msg)
    render_history(store, session_id)

    # Two-phase turn so the UI never looks frozen.
    #
    # Streamlit only repaints when a script run finishes. If we accepted the
    # prompt and immediately called a slow LLM, the user would stare at an
    # unchanged page for 30s+ with no sign anything happened. Instead: phase 1
    # stores the prompt and reruns *immediately* (so the question and a
    # "Thinking…" placeholder paint at once), and phase 2 does the slow work on
    # the next run.
    typed = st.chat_input("Ask about databases, sessions, blocking, wait types…")
    if typed:
        store.add_message(session_id, "user", typed)
        st.session_state.pending = typed
        st.rerun()

    prompt = st.session_state.pop("pending", None)
    if not prompt:
        return

    # No need to re-render the user bubble: the message is already stored, so
    # render_history() above painted it on this run.

    # Database telemetry questions are numeric, so they go to the text-to-SQL
    # agent instead of RAG — retrieval cannot SUM 2,372 rows.
    if is_dba_question(prompt):
        with st.chat_message("assistant"):
            with st.spinner("Querying session telemetry…"):
                result = ask_dba(prompt, provider_key, model)
            if result.ok:
                st.markdown(f"**DBA Telemetry Assistant**\n\n{result.text}")
                with st.expander("🔎 SQL and result"):
                    st.code(result.sql, language="sql")
                    st.markdown(result.table_markdown())
                body = f"**DBA Telemetry Assistant**\n\n{result.text}"
                cites = [f"db_session.xlsx > {len(result.rows)} rows via SQL"]
            else:
                body = f"**DBA Telemetry Assistant**\n\n⚠️ {result.error}"
                st.error(result.error)
                cites = []
            st.caption(attribution(provider_key, model, "text-to-SQL"))
        store.add_message(session_id, "assistant", body, grounded=result.ok,
                          citations=cites,
                          meta={"provider": provider_key, "model": model,
                                "mode": "text-to-sql"})
        store.touch(session_id, provider=provider_key, model=model or "")
        return

    with st.chat_message("assistant"):
        try:
            provider = make_provider(provider_key, model)
            apply_provider(fk, provider)
            history = store.history_for_llm(session_id)[:-1]  # exclude current turn
            with st.spinner("Searching official documentation…"):
                role_key = fk.pick_role(prompt).key
                answer = fk.agents[role_key].answer(prompt, history=history)
        except LLMError as exc:
            # Name the exact model in the error. "Copilot unavailable" alone is
            # misleading: the common cause is one model the account is not
            # entitled to, which a different model on the SAME provider fixes.
            label = PROVIDER_LABELS.get(provider_key, provider_key)
            err = (
                f"**{label} — `{model or 'default'}` failed.**\n\n"
                f"{exc}\n\n"
                "Try another model on this provider first (a model your account "
                "cannot access fails while others work), or switch provider in "
                "the sidebar / start the local server (`ollama serve`, LM Studio)."
            )
            st.error(err)
            st.caption(attribution(provider_key, model, strategy, retriever))
            # Persist failures too, so the error is still visible after a
            # rerun instead of vanishing from the transcript.
            store.add_message(
                session_id, "assistant", f"⚠️ {err}", grounded=False, citations=[],
                meta={"provider": provider_key, "model": model,
                      "strategy": strategy, "retriever": retriever,
                      "error": str(exc)},
            )
            return

        tag = "" if answer.grounded else "  ⚠️ _not in official docs_"
        body = f"**{answer.role_name}**{tag}\n\n{answer.text}"
        st.markdown(body)

        cites = answer.cited_sources()
        if cites:
            with st.expander(f"📚 {len(cites)} citations"):
                for c in cites:
                    st.write(f"- {c}")
        st.caption(attribution(provider_key, model, strategy, retriever))

    store.add_message(
        session_id, "assistant", body,
        grounded=answer.grounded, citations=cites,
        meta={"provider": provider_key, "model": model,
              "strategy": strategy, "retriever": retriever},
    )
    store.touch(session_id, provider=provider_key, model=model or "")


if __name__ == "__main__":
    main()
