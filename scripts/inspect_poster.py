"""Inspect where the poster template's placeholder text actually lives.

The A1 template is built from DrawingML text boxes, not body paragraphs, so
python-docx's document.paragraphs sees almost nothing. This walks the raw XML
and reports every text-bearing node with its container, so edits can target
the right element instead of guessing.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from docx import Document

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def main(path: str) -> None:
    doc = Document(path)
    body = doc.element.body

    print(f"body paragraphs : {len(doc.paragraphs)}")
    print(f"tables          : {len(doc.tables)}")
    print(f"inline shapes   : {len(doc.inline_shapes)}")
    print()

    # Every w:t in the whole package, with its ancestor chain.
    containers = Counter()
    texts = []
    for t in body.iter(f"{W}t"):
        chain = []
        node = t.getparent()
        while node is not None and node is not body:
            chain.append(node.tag.split("}")[-1])
            node = node.getparent()
        key = ">".join(reversed([c for c in chain if c in ("txbxContent", "tbl", "tc", "p", "sdtContent")]))
        containers[key] += 1
        if t.text and t.text.strip():
            texts.append((key, t.text.strip()))

    print("--- containers holding text ---")
    for k, v in containers.most_common():
        print(f"  {v:4d}  {k or '(bare body)'}")
    print()

    print("--- distinct text nodes (first 60) ---")
    seen = set()
    for key, txt in texts:
        if txt in seen:
            continue
        seen.add(txt)
        where = "TEXTBOX" if "txbxContent" in key else "BODY   "
        print(f"  [{where}] {txt[:88]}")
        if len(seen) >= 60:
            break
    print()
    print(f"total w:t nodes with text: {len(texts)}   distinct: {len(seen)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "poster_template.docx")
