"""Text-to-SQL agent for the DBA session telemetry.

Flow: **LLM writes SQL -> SQLite computes -> LLM explains the result.**

The numbers always come from the database, never from the model, so totals and
rankings are arithmetically correct. The LLM's job is translating the question
and narrating the answer — the two things it is actually good at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from factory_knowledge.providers import LLMProvider, Message, build_provider

from .store import DBAError, SessionStore, get_store

_SQL_SYSTEM = """You write SQLite queries for a DBA monitoring table.

{schema}

Rules:
- Return ONE SELECT statement and NOTHING else. No prose, no markdown fences.
- SQLite dialect only. Never modify data.
- Numeric columns (CPU, reads, writes, physical_reads, used_memory) are INTEGER.
- collection_time and duration are TEXT.
- blocking_session_id is NULL when nothing is blocking; use
  "WHERE blocking_session_id IS NOT NULL" when looking for blocking problems.
- wait_info looks like "(7ms)PAGEIOLATCH_SH:HRMS:1(*)" — the wait type follows
  the closing parenthesis.
- ALWAYS add an explicit ORDER BY before any LIMIT. A LIMIT without ORDER BY
  returns arbitrary rows and silently produces a wrong answer.
- Answer exactly what was asked. Do NOT invent extra WHERE filters (status,
  wait type, time range) that the question did not mention.
- Always add a LIMIT (<= 50) unless the question is a single aggregate.
"""

_ANSWER_SYSTEM = """You are a SQL Server DBA assistant.

Explain the query result to an engineer in plain language. Be specific: quote the
actual numbers returned. If a value is dramatically larger than the others, say
so explicitly and suggest what a DBA should investigate next.

Ground every number in the result table. Never invent figures. If the result is
empty, say the data contains no matching rows."""


@dataclass
class DBAAnswer:
    """A question, the SQL used to answer it, and the result."""

    question: str
    sql: str
    headers: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    text: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def table_markdown(self, limit: int = 20) -> str:
        """Render the result as a markdown table (the evidence for the answer)."""
        if not self.headers:
            return ""
        out = ["| " + " | ".join(self.headers) + " |",
               "|" + "|".join(["---"] * len(self.headers)) + "|"]
        for row in self.rows[:limit]:
            out.append("| " + " | ".join("" if c is None else str(c) for c in row) + " |")
        if len(self.rows) > limit:
            out.append(f"_…{len(self.rows) - limit} more rows_")
        return "\n".join(out)


def _strip_fences(text: str) -> str:
    """LLMs love markdown fences and preamble; the database wants bare SQL."""
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE).strip()
    # Anchor on the LAST statement start, not the first. Models often preface
    # the query with prose ("I'll create a query that..."), and capturing from
    # the first match drags that prose in — where words like "create" then trip
    # the safety guard and block a perfectly valid SELECT.
    matches = list(re.finditer(r"\b(?:WITH|SELECT)\b", text, re.IGNORECASE))
    if matches:
        text = text[matches[-1].start():]
    # Drop any trailing prose after the statement.
    text = text.split(";")[0]
    return text.strip().rstrip(";").strip()


class DBAAgent:
    """Answers questions about the session workbook using generated SQL."""

    def __init__(self, provider: LLMProvider | None = None,
                 store: SessionStore | None = None) -> None:
        self.store = store or get_store()
        # Text-to-SQL is much harder than chat: small local models tend to
        # invent WHERE clauses nobody asked for (measured: qwen2.5:3b added a
        # bogus status='running' filter and returned the wrong database).
        # Prefer a stronger model when one is reachable.
        self.provider = provider or self._best_provider()

    @staticmethod
    def _best_provider() -> LLMProvider:
        """Pick the strongest reachable backend for SQL generation."""
        for key in ("openai", "anthropic", "lmstudio", "ollama"):
            try:
                provider = build_provider(key)
                if provider.available().ok:
                    return provider
            except Exception:  # noqa: BLE001 - probe must never crash
                continue
        return build_provider("ollama")

    # -- steps --------------------------------------------------------------
    def write_sql(self, question: str) -> str:
        prompt = _SQL_SYSTEM.format(schema=self.store.schema_prompt())
        reply = self.provider.chat([
            Message(role="system", content=prompt),
            Message(role="user", content=question),
        ])
        return _strip_fences(reply)

    def explain(self, question: str, sql: str, headers, rows) -> str:
        table = "\n".join(
            [" | ".join(headers)] +
            [" | ".join("" if c is None else str(c) for c in r) for r in rows[:20]]
        ) or "(no rows)"
        user = (
            f"Question: {question}\n\nSQL used:\n{sql}\n\nResult:\n{table}\n\n"
            "Explain what this shows."
        )
        return self.provider.chat([
            Message(role="system", content=_ANSWER_SYSTEM),
            Message(role="user", content=user),
        ])

    # -- public API ---------------------------------------------------------
    def ask(self, question: str, retries: int = 1) -> DBAAnswer:
        """Answer a question. Retries once if the generated SQL is invalid."""
        sql = ""
        last_error = ""
        for attempt in range(retries + 1):
            try:
                sql = self.write_sql(
                    question if not last_error
                    else f"{question}\n\nYour previous SQL failed with: {last_error}\n"
                         "Return corrected SQL only."
                )
                headers, rows = self.store.run_query(sql)
            except DBAError as exc:
                last_error = str(exc)
                continue
            except Exception as exc:  # noqa: BLE001 - provider/network failures
                return DBAAnswer(question, sql, error=f"LLM unavailable: {exc}")

            try:
                text = self.explain(question, sql, headers, rows)
            except Exception as exc:  # noqa: BLE001
                text = f"(Could not generate explanation: {exc})"
            return DBAAnswer(question, sql, headers, rows, text)

        return DBAAnswer(question, sql, error=last_error or "Could not build a query.")
