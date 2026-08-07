"""Terminal chat for the Factory Knowledge assistant.

Run it::

    python cli.py                          # auto-routes to a specialist
    python cli.py --role maintenance       # talk to one specialist directly
    python cli.py --ask "What is alarm E-204?"   # one-shot

No API key needed to try it — it answers in retrieval-only mode and tells you so.
Add OPENAI_API_KEY to .env for fully synthesized, cited answers.
"""

from __future__ import annotations

import argparse
import sys

from factory_knowledge import FactoryKnowledge
from factory_knowledge.config import settings
from factory_knowledge.llm import LLMError

# Make sure Unicode (bullets, arrows) renders on Windows terminals too.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - older/odd streams
    pass


def _ask_safely(fk: FactoryKnowledge, question: str, role_key: str | None):
    """Ask, but turn LLM failures into a clear message instead of a crash."""
    try:
        return fk.ask(question, role_key=role_key)
    except LLMError as exc:
        print(f"\n[LLM unavailable] {exc}")
        print(
            "Tip: check OPENAI_API_KEY in your .env (a wrong/expired key returns "
            "a 401), or set it blank to run in retrieval-only mode.\n"
        )
        return None


def _print_answer(answer) -> None:
    if answer is None:
        return
    flag = "" if answer.grounded else "  (abstained — not in official docs)"
    print(f"\n[{answer.role_name}]{flag}")
    print(answer.text)
    sources = answer.cited_sources()
    if sources:
        print("\nCitations:")
        for s in sources:
            print(f"  - {s}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Database Knowledge Assistant — docs + telemetry")
    parser.add_argument("--role", help="Force a specialist by key (maintenance, safety, quality)")
    parser.add_argument("--ask", help="Ask a single question and exit")
    args = parser.parse_args()

    fk = FactoryKnowledge()
    counts = fk.warmup()

    mode = "LLM" if settings.llm_enabled else "retrieval-only (no API key)"
    print("=" * 66)
    print("  Database Knowledge Assistant — docs + telemetry")
    print("=" * 66)
    print(fk.describe_team())
    print(f"\nIndexed chunks: {counts}")
    print(f"Mode: {mode} | Retriever: {settings.retriever} | Router: {settings.router}")

    if args.ask:
        _print_answer(_ask_safely(fk, args.ask, args.role))
        return 0

    print("\nAsk a question. Commands: /role <key>, /team, /quit\n")
    forced_role = args.role
    while True:
        try:
            question = input("tech > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nStay safe out there!")
            return 0
        if not question:
            continue
        if question in {"/quit", "/exit", "/q"}:
            print("Stay safe out there!")
            return 0
        if question == "/team":
            print(fk.describe_team())
            continue
        if question.startswith("/role"):
            parts = question.split()
            forced_role = parts[1] if len(parts) > 1 else None
            print(f"(now talking to: {forced_role or 'auto-route'})")
            continue
        try:
            _print_answer(_ask_safely(fk, question, forced_role))
        except Exception as exc:  # noqa: BLE001 - keep the REPL alive
            print(f"[error] {exc}")


if __name__ == "__main__":
    sys.exit(main())
