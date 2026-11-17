"""Dump every text-bearing paragraph in the poster template, joined per paragraph.

Runs are fragmented (headings are split letter-by-letter), so the only sane
unit to match on is the paragraph. Prints an index for each so the filler can
target them unambiguously.
"""
from __future__ import annotations

import sys

from docx import Document

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def para_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(f"{W}t"))


def all_paragraphs(doc):
    """Body paragraphs AND paragraphs inside drawing text boxes, in document order."""
    body = doc.element.body
    for p in body.iter(f"{W}p"):
        # skip paragraphs that merely *contain* a textbox; keep the inner ones
        if p.find(f".//{W}txbxContent") is not None:
            continue
        yield p


def main(path: str) -> None:
    doc = Document(path)
    for i, p in enumerate(all_paragraphs(doc)):
        txt = para_text(p).strip()
        if not txt:
            continue
        runs = len(p.findall(f".//{W}t"))
        print(f"[{i:4d}] runs={runs:3d} | {txt[:150]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "poster_template.docx")
