"""Tests for the DBA text-to-SQL package.

Two layers, deliberately separated:

  LAYER 1 (default) — deterministic. No LLM, no network. Checks loading, the
  safety guard, SQL cleanup, and routing. Runs in under a second, so it can gate
  every commit.

  LAYER 2 (opt-in) — the LLM actually writing SQL. Non-deterministic and slow,
  so it only runs with --llm. Instead of asserting on exact SQL text (which
  changes run to run), it asserts the *answer* matches a known-correct value
  computed independently by hand-written SQL. That is the only honest way to
  test a generative step.

Usage::

    .venv/Scripts/python.exe tests/test_dba.py            # fast, deterministic
    .venv/Scripts/python.exe tests/test_dba.py --llm      # + real LLM checks
    .venv/Scripts/python.exe tests/test_dba.py --llm --provider openai
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dba.agent import _strip_fences  # noqa: E402
from dba.store import DBAError, get_store  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _results.append((PASS if condition else FAIL, name, detail))


# ---------------------------------------------------------------------------
# LAYER 1 — deterministic
# ---------------------------------------------------------------------------
def test_workbook_loads(store) -> None:
    check("workbook loads all rows", store.row_count == 2372,
          f"got {store.row_count}, expected 2372")
    check("all 15 columns present", len(store.columns) == 15,
          f"got {len(store.columns)}")
    names = [c.name for c in store.columns]
    for required in ("database_name", "CPU", "blocking_session_id", "wait_info"):
        check(f"column {required!r} exists", required in names)


def test_numeric_columns_are_numeric(store) -> None:
    """If CPU loads as TEXT, SUM() silently returns garbage — the bug that
    would quietly corrupt every aggregate answer."""
    _, rows = store.run_query("SELECT SUM(CPU) FROM db_sessions")
    total = rows[0][0]
    check("CPU sums as a number", isinstance(total, int) and total > 0,
          f"got {total!r}")
    _, rows = store.run_query(
        "SELECT database_name, SUM(CPU) c FROM db_sessions "
        "GROUP BY 1 ORDER BY c DESC LIMIT 1"
    )
    check("top CPU database is db06", rows[0][0] == "db06", f"got {rows[0][0]}")
    check("top CPU total is 60214551", rows[0][1] == 60214551, f"got {rows[0][1]}")


def test_data_dictionary(store) -> None:
    meanings = {c.name: c.meaning for c in store.columns}
    check("column meanings loaded from 'explanation' sheet",
          bool(meanings.get("wait_info")), "wait_info has no description")
    check("schema prompt mentions row count",
          "2372" in store.schema_prompt())


def test_safety_guard_blocks_writes(store) -> None:
    attacks = [
        ("DROP TABLE db_sessions", "drop"),
        ("DELETE FROM db_sessions", "delete"),
        ("UPDATE db_sessions SET CPU=0", "update"),
        ("INSERT INTO db_sessions VALUES (1)", "insert"),
        ("SELECT 1; DROP TABLE db_sessions", "stacked statement"),
        ("ALTER TABLE db_sessions ADD c INT", "alter"),
        ("ATTACH DATABASE 'x.db' AS x", "attach"),
        ("PRAGMA table_info(db_sessions)", "pragma"),
        ("", "empty query"),
    ]
    for sql, label in attacks:
        try:
            store.run_query(sql)
            check(f"blocks {label}", False, "query was ALLOWED")
        except DBAError:
            check(f"blocks {label}", True)

    # And the table must be untouched after all that.
    check("table survived the attacks",
          store.run_query("SELECT COUNT(*) FROM db_sessions")[1][0][0] == 2372)


def test_safety_guard_allows_reads(store) -> None:
    """A guard that blocks legitimate queries is just as broken as one that
    lets writes through. This is the regression test for the false positive
    found in the UI."""
    legit = [
        "SELECT * FROM db_sessions LIMIT 3",
        "SELECT database_name, SUM(CPU) c FROM db_sessions GROUP BY 1 ORDER BY c DESC LIMIT 5",
        "WITH t AS (SELECT CPU FROM db_sessions) SELECT SUM(CPU) FROM t",
        # 'update'/'create' appearing inside a string literal is harmless.
        "SELECT * FROM db_sessions WHERE program_name='update service' LIMIT 2",
        "SELECT * FROM db_sessions WHERE login_name='create_user' LIMIT 2",
    ]
    for sql in legit:
        try:
            store.run_query(sql)
            check(f"allows: {sql[:46]}…", True)
        except DBAError as exc:
            check(f"allows: {sql[:46]}…", False, f"FALSE POSITIVE: {exc}")


def test_sql_cleanup() -> None:
    """The generated text must be reduced to bare SQL."""
    cases = [
        ("```sql\nSELECT 1\n```", "SELECT 1"),
        ("SELECT 1;", "SELECT 1"),
        # Prose preamble containing 'create' must not survive — this was the
        # real bug that made the guard reject a valid SELECT in the UI.
        ("Sure! I will create a query.\n```sql\nSELECT 1\n```", "SELECT 1"),
        ("Here is the query:\nSELECT 1", "SELECT 1"),
    ]
    for raw, expected in cases:
        got = _strip_fences(raw)
        check(f"cleans {raw[:30]!r}…", got == expected, f"got {got!r}")

    cleaned = _strip_fences("I'll create a query.\n```sql\nSELECT 1\n```")
    check("cleaned SQL has no prose keywords", "create" not in cleaned.lower(),
          f"got {cleaned!r}")


def test_routing() -> None:
    """DBA questions must go to SQL; factory questions must stay on RAG."""
    try:
        from ui_helpers import is_dba_question
    except Exception as exc:  # noqa: BLE001
        check("routing importable", False, str(exc))
        return

    dba_qs = [
        "which database used the most CPU?",
        "what are the top wait types?",
        "show me blocking sessions",
        "how many sessions are suspended?",
    ]
    factory_qs = [
        "What does alarm code E-204 mean?",
        "What PPE is required in the grinding area?",
        "How do I calibrate the bore gauge?",
        "What are the lockout tagout steps?",
        "What is the tolerance for the shaft diameter?",
    ]
    for q in dba_qs:
        check(f"routes to DBA: {q[:38]}…", is_dba_question(q))
    for q in factory_qs:
        check(f"stays on RAG: {q[:38]}…", not is_dba_question(q))


def test_known_answers(store) -> None:
    """Ground truth computed by hand-written SQL. These are the values the LLM
    path is later checked against."""
    _, rows = store.run_query(
        "SELECT blocking_session_id, COUNT(*) n FROM db_sessions "
        "WHERE blocking_session_id IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT 1"
    )
    check("top blocker is session 114", rows[0][0] == 114, f"got {rows[0][0]}")
    check("top blocker blocks 14 times", rows[0][1] == 14, f"got {rows[0][1]}")

    _, rows = store.run_query(
        "SELECT status, COUNT(*) n FROM db_sessions GROUP BY 1 ORDER BY n DESC"
    )
    check("4 distinct session states", len(rows) == 4, f"got {len(rows)}")
    check("most common status is suspended", rows[0][0] == "suspended",
          f"got {rows[0][0]}")


# ---------------------------------------------------------------------------
# LAYER 2 — the LLM actually generating SQL (opt-in)
# ---------------------------------------------------------------------------
def test_llm_generates_correct_answers(store, provider_key: str) -> None:
    """Assert on the ANSWER, not the SQL text.

    Two different-but-valid queries can produce the same correct row, so
    asserting on exact SQL would fail for no reason. What matters is whether
    the number is right.
    """
    from dba.agent import DBAAgent
    from factory_knowledge.providers import build_provider

    agent = DBAAgent(provider=build_provider(provider_key), store=store)

    cases = [
        ("which database used the most CPU in total?", ("db06", 60214551)),
        ("which session blocks other sessions most often?", (114, 14)),
    ]
    for question, expected in cases:
        answer = agent.ask(question)
        if not answer.ok:
            check(f"[llm] {question[:40]}…", False, answer.error)
            continue
        flat = [c for row in answer.rows for c in row]
        hits = [e for e in expected if e in flat]
        check(f"[llm] {question[:40]}…", len(hits) == len(expected),
              f"expected {expected} in {answer.rows[:3]} | SQL: {' '.join(answer.sql.split())[:90]}")


def main(argv: list[str]) -> int:
    use_llm = "--llm" in argv
    provider = "ollama"
    if "--provider" in argv:
        provider = argv[argv.index("--provider") + 1]

    try:
        store = get_store()
    except DBAError as exc:
        print(f"Cannot load workbook: {exc}")
        return 2

    test_workbook_loads(store)
    test_numeric_columns_are_numeric(store)
    test_data_dictionary(store)
    test_safety_guard_blocks_writes(store)
    test_safety_guard_allows_reads(store)
    test_sql_cleanup()
    test_routing()
    test_known_answers(store)

    if use_llm:
        print(f"(running LLM checks against provider={provider} — slow)\n")
        test_llm_generates_correct_answers(store, provider)

    failures = 0
    for status, name, detail in _results:
        line = f"{status}  {name}"
        if status == FAIL:
            failures += 1
            line += f"\n      -> {detail}"
        print(line)

    total = len(_results)
    print(f"\n{total - failures}/{total} passed.")
    if not use_llm:
        print("Deterministic tests only. Add --llm to test SQL generation.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
