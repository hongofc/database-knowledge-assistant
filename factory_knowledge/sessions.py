"""Persistent chat sessions — the chatbot's long-term memory.

Every conversation, message, citation, and the provider/model/strategy used to
produce it are stored in a local SQLite file. That gives you:

* **Resume** — reopen any past conversation and keep going.
* **Provenance** — each answer records which provider, model, chunking
  strategy, and retriever produced it, so a demo can show *how* settings
  changed the answer.
* **A growing knowledge trail** — past Q&A is searchable, so the assistant can
  surface "you asked something similar before" instead of starting cold.

SQLite is deliberate: zero setup, one file, works air-gapped on the factory
floor, and survives restarts.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    provider    TEXT,
    model       TEXT,
    meta        TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  REAL NOT NULL,
    grounded    INTEGER,
    citations   TEXT,
    meta        TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""


@dataclass
class StoredMessage:
    role: str
    content: str
    created_at: float
    grounded: bool | None = None
    citations: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class SessionInfo:
    id: str
    title: str
    created_at: float
    updated_at: float
    provider: str = ""
    model: str = ""
    message_count: int = 0


class SessionStore:
    """Thin SQLite wrapper for conversations and their messages."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = str(path or settings.sessions_db)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # -- sessions -----------------------------------------------------------
    def create_session(self, title: str = "New chat", provider: str = "",
                       model: str = "", meta: dict | None = None) -> str:
        sid = uuid.uuid4().hex[:12]
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id,title,created_at,updated_at,provider,model,meta)"
                " VALUES (?,?,?,?,?,?,?)",
                (sid, title, now, now, provider, model, json.dumps(meta or {})),
            )
        return sid

    def list_sessions(self, limit: int = 50) -> list[SessionInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS n"
                " FROM sessions s ORDER BY s.updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            SessionInfo(
                id=r["id"], title=r["title"], created_at=r["created_at"],
                updated_at=r["updated_at"], provider=r["provider"] or "",
                model=r["model"] or "", message_count=r["n"],
            )
            for r in rows
        ]

    def rename_session(self, session_id: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sessions SET title=? WHERE id=?", (title, session_id))

    def delete_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    def touch(self, session_id: str, provider: str = "", model: str = "") -> None:
        """Bump updated_at (and provider/model if switched mid-conversation)."""
        with self._connect() as conn:
            if provider or model:
                conn.execute(
                    "UPDATE sessions SET updated_at=?, provider=?, model=? WHERE id=?",
                    (time.time(), provider, model, session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET updated_at=? WHERE id=?", (time.time(), session_id)
                )

    # -- messages -----------------------------------------------------------
    def add_message(self, session_id: str, role: str, content: str,
                    grounded: bool | None = None, citations: list[str] | None = None,
                    meta: dict | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id,role,content,created_at,grounded,citations,meta)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    session_id, role, content, time.time(),
                    None if grounded is None else int(grounded),
                    json.dumps(citations or []), json.dumps(meta or {}),
                ),
            )
            conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (time.time(), session_id))
        # First user message makes a far better title than "New chat".
        if role == "user":
            self._maybe_autotitle(session_id, content)

    def _maybe_autotitle(self, session_id: str, content: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT title FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row and row["title"] in ("New chat", "", None):
                title = content.strip().replace("\n", " ")[:60]
                conn.execute("UPDATE sessions SET title=? WHERE id=?", (title, session_id))

    def get_messages(self, session_id: str) -> list[StoredMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,)
            ).fetchall()
        out: list[StoredMessage] = []
        for r in rows:
            out.append(
                StoredMessage(
                    role=r["role"], content=r["content"], created_at=r["created_at"],
                    grounded=None if r["grounded"] is None else bool(r["grounded"]),
                    citations=json.loads(r["citations"] or "[]"),
                    meta=json.loads(r["meta"] or "{}"),
                )
            )
        return out

    def search(self, query: str, limit: int = 20) -> list[tuple[str, str, str]]:
        """Full-text-ish search across past messages -> (session_id, title, snippet)."""
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT m.session_id, s.title, m.content FROM messages m"
                " JOIN sessions s ON s.id=m.session_id"
                " WHERE m.content LIKE ? ORDER BY m.created_at DESC LIMIT ?",
                (like, limit),
            ).fetchall()
        return [(r["session_id"], r["title"], r["content"][:200]) for r in rows]

    def history_for_llm(self, session_id: str, max_turns: int = 6) -> list[dict]:
        """Recent turns as chat messages, so follow-ups ('and the next step?') work."""
        msgs = [m for m in self.get_messages(session_id) if m.role in ("user", "assistant")]
        return [{"role": m.role, "content": m.content} for m in msgs[-max_turns * 2:]]
