"""Smoke tests — prove the pipeline works end-to-end with no API key.

Run with::

    pytest            # if pytest is installed
    python tests/test_smoke.py   # also runs standalone

These avoid any network/LLM calls so they pass offline and in CI. They also
cover the two enterprise-RAG features: section/page citations and the
hallucination guardrail (abstain when nothing relevant is found).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory_knowledge import FactoryKnowledge
from factory_knowledge.config import Settings
from factory_knowledge.ingest import chunk_document
from factory_knowledge.rag.base import Chunk, Document
from factory_knowledge.rag.keyword_retriever import KeywordRetriever, tokenize


def _offline_settings(min_score: float = 0.0) -> Settings:
    cfg = Settings()
    cfg.openai_api_key = None
    cfg.llm_provider = "openai"  # not enabled without a key -> fallback mode
    cfg.retriever = "keyword"
    cfg.router = "keyword"
    cfg.min_score = min_score
    return cfg


def test_tokenize_keeps_alphanumeric_codes():
    toks = tokenize("What does alarm E204 mean?")
    assert "e204" in toks
    assert "the" not in tokenize("the alarm")


def test_chunking_captures_section_headings():
    text = "# Troubleshooting\n\n" + ("Spindle does not start. " * 40)
    doc = Document(text=text, source="m.md", role="maintenance")
    chunks = chunk_document(doc, chunk_size=300, overlap=50)
    assert chunks
    assert all(c.metadata.get("section") == "Troubleshooting" for c in chunks)


def test_chunking_captures_pdf_page_marker():
    text = "<<<PAGE:1>>>\n\nIntro paragraph.\n\n<<<PAGE:2>>>\n\nEmergency stop steps."
    doc = Document(text=text, source="e.pdf", role="safety")
    chunks = chunk_document(doc)
    pages = {c.metadata.get("page") for c in chunks}
    assert pages == {1, 2}
    # The page marker text itself must not leak into chunk content.
    assert all("<<<PAGE" not in c.text for c in chunks)


def test_citation_formats_source_page_section():
    c = Chunk(text="x", source="manual.pdf", role="maintenance",
              metadata={"page": 3, "section": "Faults"})
    assert c.citation() == "manual.pdf (p.3) > Faults"


def test_keyword_retriever_ranks_relevant_chunk_first():
    retriever = KeywordRetriever()
    retriever.index([
        Chunk(text="Alarm E-204 indicates spindle overload on the CNC mill.",
              source="codes.md", role="maintenance"),
        Chunk(text="Always wear safety goggles in the grinding area.",
              source="ppe.md", role="safety"),
    ])
    top = retriever.retrieve("what is alarm E-204", top_k=1)
    assert top and top[0].source == "codes.md"


def test_router_picks_right_specialist():
    cfg = _offline_settings()
    fk = FactoryKnowledge(cfg)
    assert fk.pick_role("What does alarm code E-204 mean?").key == "maintenance"
    assert fk.pick_role("What PPE and lockout steps before cleaning?").key == "safety"
    assert fk.pick_role("What is the calibration tolerance for the gauge?").key == "quality"


def test_end_to_end_answer_with_citation():
    cfg = _offline_settings()
    fk = FactoryKnowledge(cfg)
    counts = fk.warmup()
    assert sum(counts.values()) > 0

    answer = fk.ask("What does alarm code E-204 mean?")
    assert answer.grounded is True
    assert answer.cited_sources()  # at least one verifiable citation
    # In no-LLM mode the answer echoes retrieved context mentioning the code.
    assert "204" in answer.text


def test_guardrail_abstains_when_nothing_relevant():
    # A very high score floor forces every hit below the trust threshold.
    cfg = _offline_settings(min_score=999.0)
    fk = FactoryKnowledge(cfg)
    fk.warmup()
    answer = fk.ask("What does alarm code E-204 mean?")
    assert answer.grounded is False
    assert answer.sources == []
    # Abstain message is grounded-safe: it points to official docs / escalation.
    assert "official" in answer.text.lower()
    assert "escalate" in answer.text.lower()


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    print(f"\n{'All tests passed.' if not failures else f'{failures} test(s) failed.'}")
    sys.exit(1 if failures else 0)
