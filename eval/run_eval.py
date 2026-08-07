"""Retrieval evaluation harness — prove the chunking work actually helps.

Runs the golden question set against every chunking strategy and reports
standard IR metrics, so "advanced chunking" becomes a number instead of a
claim. This is what turns a demo into evidence.

Metrics
-------
Hit@k       fraction of questions where the correct document appears in top-k
MRR         mean reciprocal rank of the first correct document (rank quality)
Context     fraction where the expected *text* survived chunking intact
            (this is the metric that exposes severed tables)
Abstain     fraction of adversarial questions correctly refused

Usage::

    python -m eval.run_eval                      # all strategies, keyword retriever
    python -m eval.run_eval --retriever vector   # semantic retrieval
    python -m eval.run_eval --strategies fixed,metadata_aware
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory_knowledge.config import DATA_DIR, settings  # noqa: E402
from factory_knowledge.ingest import build_chunks  # noqa: E402
from factory_knowledge.rag.base import build_retriever  # noqa: E402
from factory_knowledge.roles import load_roles  # noqa: E402

GOLDEN = Path(__file__).parent / "golden_set.yaml"


def load_cases() -> list[dict]:
    import yaml

    with open(GOLDEN, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["cases"]


def evaluate(strategy: str, retriever_kind: str, top_k: int = 5) -> dict:
    """Index the whole corpus with ``strategy`` and score the golden set."""
    roles = load_roles()
    t0 = time.time()

    all_chunks = []
    for role in roles:
        all_chunks.extend(build_chunks(DATA_DIR / role.key, role.key, strategy=strategy))
    index_time = time.time() - t0

    retriever = build_retriever(retriever_kind)
    retriever.index(all_chunks)

    cases = load_cases()
    grounded = [c for c in cases if not c.get("abstain")]
    adversarial = [c for c in cases if c.get("abstain")]

    hits, rr, ctx_ok = 0, 0.0, 0
    failures: list[str] = []

    for case in grounded:
        results = retriever.retrieve(case["question"], top_k=top_k)
        rank = None
        for i, chunk in enumerate(results, start=1):
            if case["expect_source"].lower() in chunk.source.lower():
                rank = i
                break
        if rank:
            hits += 1
            rr += 1.0 / rank
        else:
            failures.append(f"{case['id']}: missed {case['expect_source']}")

        want = case.get("expect_text")
        if want:
            if any(want.lower() in c.text.lower() for c in results):
                ctx_ok += 1
        else:
            ctx_ok += 1  # nothing specific demanded

    # Adversarial: correct behaviour is every hit scoring below the floor.
    abstained = 0
    for case in adversarial:
        results = retriever.retrieve(case["question"], top_k=top_k)
        best = max((c.score for c in results), default=0.0)
        if not results or best < max(settings.min_score, 0.01):
            abstained += 1

    n = len(grounded) or 1
    return {
        "strategy": strategy,
        "chunks": len(all_chunks),
        "avg_chars": sum(len(c.text) for c in all_chunks) // max(1, len(all_chunks)),
        "index_s": round(index_time, 2),
        "hit_at_k": hits / n,
        "mrr": rr / n,
        "context_ok": ctx_ok / n,
        "abstain": abstained / max(1, len(adversarial)),
        "failures": failures,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare chunking strategies on retrieval quality.")
    ap.add_argument("--strategies", default="fixed,recursive,semantic,metadata_aware")
    ap.add_argument("--retriever", default=settings.retriever, help="keyword | vector | hybrid")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    print(f"\nRetriever: {args.retriever}   top_k={args.top_k}   "
          f"cases={len(load_cases())}\n")

    header = f"{'strategy':<16}{'chunks':>7}{'avg':>6}{'Hit@k':>8}{'MRR':>7}{'Ctx':>7}{'Abst':>7}{'idx_s':>7}"
    print(header)
    print("-" * len(header))

    rows = []
    for strat in strategies:
        try:
            r = evaluate(strat, args.retriever, args.top_k)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"{strat:<16} ERROR: {exc}")
            continue
        rows.append(r)
        print(f"{r['strategy']:<16}{r['chunks']:>7}{r['avg_chars']:>6}"
              f"{r['hit_at_k']:>8.2f}{r['mrr']:>7.2f}{r['context_ok']:>7.2f}"
              f"{r['abstain']:>7.2f}{r['index_s']:>7.2f}")

    if rows:
        best = max(rows, key=lambda r: (r["mrr"], r["context_ok"]))
        print(f"\nBest by MRR: {best['strategy']}")
        for r in rows:
            if r["failures"]:
                print(f"\n  {r['strategy']} misses:")
                for f in r["failures"]:
                    print(f"    - {f}")


if __name__ == "__main__":
    main()
