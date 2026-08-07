"""Command-line entry point:  python -m dba "your question"

Examples::

    python -m dba --schema
    python -m dba "which database used the most CPU?"
    python -m dba --sql "SELECT status, COUNT(*) FROM db_sessions GROUP BY 1"
"""

from __future__ import annotations

import argparse
import sys

from factory_knowledge.providers import build_provider

from .agent import DBAAgent
from .store import DBAError, get_store


def _print_table(headers, rows, limit=25) -> None:
    if not headers:
        return
    widths = [len(h) for h in headers]
    shown = rows[:limit]
    for row in shown:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len("" if cell is None else str(cell)))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for row in shown:
        print("  ".join(
            ("" if c is None else str(c)).ljust(widths[i]) for i, c in enumerate(row)
        ))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m dba",
        description="Ask questions about the SQL Server session telemetry.",
    )
    parser.add_argument("question", nargs="*", help="natural-language question")
    parser.add_argument("--sql", help="run a raw SELECT instead of asking the LLM")
    parser.add_argument("--schema", action="store_true", help="show the table schema")
    parser.add_argument("--provider", default="ollama", help="LLM provider key")
    parser.add_argument("--model", default=None, help="model name")
    args = parser.parse_args(argv)

    try:
        store = get_store()
    except DBAError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.schema:
        print(store.schema_prompt())
        return 0

    if args.sql:
        try:
            headers, rows = store.run_query(args.sql)
        except DBAError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        _print_table(headers, rows)
        return 0

    question = " ".join(args.question).strip()
    if not question:
        parser.print_help()
        return 0

    agent = DBAAgent(provider=build_provider(args.provider, model=args.model))
    answer = agent.ask(question)
    if not answer.ok:
        print(f"Error: {answer.error}", file=sys.stderr)
        return 1

    print(f"\nSQL:\n  {answer.sql}\n")
    _print_table(answer.headers, answer.rows)
    print(f"\n{answer.text}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
