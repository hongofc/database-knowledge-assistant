"""Collect real, quotable evidence for the capstone poster.

Runs a battery of questions through the live stack and records, per question:
latency, grounded/abstain, top retrieval score, and cited sources. Everything
printed here is measured - nothing is estimated.

Run:  .venv/Scripts/python.exe scripts/poster_evidence.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory_knowledge.config import settings, _default_min_score
from factory_knowledge.orchestrator import FactoryKnowledge

GROUNDED = [
    "What does alarm code E-204 mean?",
    "What PPE is required in the grinding area?",
    "What are the lockout tagout steps?",
    "What is the chemical spill procedure?",
    "How often is preventive maintenance scheduled?",
    "What does the quality control SOP require for first article inspection?",
    "What should I do when the conveyor belt is slipping?",
    "What are the changeover steps between product variants?",
]

ABSTAIN = [
    "What does alarm code Z-999 mean?",
    "What is the CEO's salary?",
    "Who won the world cup in 2010?",
    "What is our 2027 headcount plan?",
]

DBA = [
    "which database used the most CPU in total?",
    "which session blocks other sessions most often?",
    "what are the top 5 wait types?",
]


def main() -> None:
    t0 = time.perf_counter()
    fk = FactoryKnowledge(settings)
    counts = fk.warmup()
    index_s = time.perf_counter() - t0

    print(f"retriever      : {settings.retriever}")
    print(f"embedding model: {settings.embedding_model}")
    print(f"chunk strategy : {settings.chunk_strategy}")
    print(f"abstain floor  : {_default_min_score(settings.retriever)}")
    print(f"chunks indexed : {counts} (total {sum(counts.values())})")
    print(f"cold index time: {index_s:.1f}s")
    print()

    rows = []

    def run(q: str, bucket: str) -> None:
        t = time.perf_counter()
        res = fk.ask(q)
        dt = time.perf_counter() - t
        role = fk.pick_role(q)
        hits = fk.agents[role.key].retriever.retrieve(q, top_k=1)
        top = round(getattr(hits[0], "score", 0.0), 4) if hits else 0.0
        srcs = res.cited_sources() if callable(res.cited_sources) else res.cited_sources
        rows.append(
            {
                "bucket": bucket,
                "q": q,
                "grounded": bool(res.grounded),
                "top_score": top,
                "latency_s": round(dt, 2),
                "role": res.role_name,
                "sources": list(srcs or []),
            }
        )
        flag = "GROUNDED" if res.grounded else "ABSTAIN "
        print(f"[{flag}] {dt:5.2f}s  top={top:<7} {q[:52]}")

    print("--- should ANSWER (in corpus) ---")
    for q in GROUNDED:
        run(q, "grounded")
    print()
    print("--- should ABSTAIN (not in corpus) ---")
    for q in ABSTAIN:
        run(q, "abstain")
    print()

    print("--- text-to-SQL (telemetry) ---")
    for q in DBA:
        t = time.perf_counter()
        try:
            from dba import answer as dba_answer  # type: ignore

            out = dba_answer(q)
            txt = str(out)[:120]
            ok = True
        except Exception as exc:  # noqa: BLE001
            txt = f"ERROR: {exc}"
            ok = False
        dt = time.perf_counter() - t
        rows.append({"bucket": "dba", "q": q, "ok": ok, "latency_s": round(dt, 2)})
        print(f"[{'OK ' if ok else 'ERR'}] {dt:5.2f}s  {q[:46]} -> {txt[:70]}")

    g = [r for r in rows if r["bucket"] == "grounded"]
    a = [r for r in rows if r["bucket"] == "abstain"]
    hit = sum(1 for r in g if r["grounded"])
    miss = sum(1 for r in a if not r["grounded"])
    lat = [r["latency_s"] for r in g if r["grounded"]]

    print()
    print("=== SUMMARY ===")
    print(f"answered when it should : {hit}/{len(g)}")
    print(f"abstained when it should: {miss}/{len(a)}")
    if lat:
        print(f"answer latency          : min {min(lat):.1f}s  median {sorted(lat)[len(lat)//2]:.1f}s  max {max(lat):.1f}s")
    gs = [r["top_score"] for r in g]
    ads = [r["top_score"] for r in a]
    print(f"grounded top-score range   : {min(gs):.4f} - {max(gs):.4f}")
    print(f"adversarial top-score range: {min(ads):.4f} - {max(ads):.4f}")
    print(f"cleanly separable          : {min(gs) > max(ads)}")

    out = Path("poster_evidence.json")
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
