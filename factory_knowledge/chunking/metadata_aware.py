"""Metadata-aware chunking — respect document *structure*, not just size.

Factory documentation is not prose. It is error-code tables, numbered
procedures, PM schedules, and log entries. Splitting those by character count
destroys them: the classic failure is an error-code table whose header row
("Code | Meaning | Action") lands in chunk 1 while the E-204 row lands in
chunk 2 — so retrieving the row gives the LLM digits with no column meaning.

This strategy:

* keeps **table rows atomic** and re-attaches the table header to every chunk
  of that table, so a retrieved row is always self-describing;
* keeps **numbered/bulleted procedures** together, never orphaning a step;
* prefixes each chunk with a **heading breadcrumb** (``H1 > H2 > H3``) so the
  embedding sees the document context, not just the fragment;
* tags rich metadata (``content_type``, ``heading_path``, ``codes``) which the
  retriever can filter on — e.g. jump straight to chunks containing "E-204".

That metadata is what turns "advanced chunking" into measurable retrieval gain.
"""

from __future__ import annotations

import re

from ..rag.base import Chunk, Document
from .base import HEADING_RE, PAGE_RE, TABLE_ROW_RE, ChunkStrategy, register

# Equipment/alarm codes: E-204, ALM1234, PM-07, SOP LOTO-01.
CODE_RE = re.compile(r"\b[A-Z]{1,5}[-\s]?\d{2,5}\b")
LIST_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+")


def _classify(block: str) -> str:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if not lines:
        return "empty"
    table_like = sum(1 for ln in lines if TABLE_ROW_RE.match(ln))
    if table_like >= max(2, len(lines) * 0.6):
        return "table"
    listy = sum(1 for ln in lines if LIST_ITEM_RE.match(ln))
    if listy >= max(2, len(lines) * 0.5):
        return "procedure"
    return "prose"


@register
class MetadataAwareChunker(ChunkStrategy):
    key = "metadata_aware"
    label = "Metadata-aware (structure preserving)"
    description = "Keeps tables/procedures atomic, adds heading breadcrumbs and code tags."

    def __init__(self, chunk_size: int = 800, overlap: int = 120,
                 add_breadcrumb: bool = True, **kwargs) -> None:
        super().__init__(chunk_size, overlap, **kwargs)
        self.add_breadcrumb = add_breadcrumb

    def split(self, doc: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        heading_stack: list[str] = []
        page: int | None = None

        for para in [p.strip() for p in doc.text.split("\n\n") if p.strip()]:
            page_match = PAGE_RE.match(para)
            if page_match:
                page = int(page_match.group(1))
                continue

            first_line = para.splitlines()[0].strip()
            heading = HEADING_RE.match(first_line)
            if heading:
                level = len(heading.group(1))
                # Maintain an H1>H2>H3 breadcrumb path.
                heading_stack = heading_stack[: level - 1]
                while len(heading_stack) < level - 1:
                    heading_stack.append("")
                heading_stack.append(heading.group(2).strip())
                body = "\n".join(para.splitlines()[1:]).strip()
                if not body:
                    continue
                para = body

            path = [h for h in heading_stack if h]
            section = path[-1] if path else ""
            breadcrumb = " > ".join(path)
            kind = _classify(para)

            for piece in self._split_block(para, kind):
                text = piece
                if self.add_breadcrumb and breadcrumb and not text.startswith(breadcrumb):
                    text = f"[{breadcrumb}]\n{piece}"
                # Extract codes from the final text (incl. breadcrumb) so a
                # chunk under an "E-204" heading is tagged even when the body
                # itself only says "Cause:/Action:".
                codes = sorted(set(CODE_RE.findall(text)))
                chunk = self._chunk(
                    text, doc, section, page,
                    content_type=kind,
                    heading_path=breadcrumb,
                    # Chroma metadata must be scalar -> store codes as a string.
                    codes=",".join(codes) if codes else "",
                )
                if chunk:
                    chunks.append(chunk)
        return chunks

    def _split_block(self, block: str, kind: str) -> list[str]:
        """Split a block without breaking its structural unit."""
        if len(block) <= self.chunk_size:
            return [block]

        lines = [ln for ln in block.splitlines() if ln.strip()]
        if kind == "table":
            return self._split_table(lines)
        if kind == "procedure":
            return self._split_by_units(lines, LIST_ITEM_RE)
        # Prose: pack whole lines up to the budget.
        return self._pack(lines, "\n")

    def _split_table(self, lines: list[str]) -> list[str]:
        """Chunk a table by rows, repeating the header in every chunk."""
        header = lines[0]
        # Markdown separator row (|---|---|) belongs with the header.
        start = 1
        if len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= {"-", " ", ":"}:
            header = f"{header}\n{lines[1]}"
            start = 2

        out: list[str] = []
        buffer: list[str] = []
        for row in lines[start:]:
            candidate = "\n".join([header] + buffer + [row])
            if len(candidate) > self.chunk_size and buffer:
                out.append("\n".join([header] + buffer))
                buffer = [row]
            else:
                buffer.append(row)
        if buffer:
            out.append("\n".join([header] + buffer))
        return out or ["\n".join(lines)]

    def _split_by_units(self, lines: list[str], marker: re.Pattern) -> list[str]:
        """Group continuation lines with their list item, then pack groups."""
        units: list[str] = []
        current: list[str] = []
        for line in lines:
            if marker.match(line) and current:
                units.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            units.append("\n".join(current))
        return self._pack(units, "\n")

    def _pack(self, units: list[str], joiner: str) -> list[str]:
        """Greedily merge units up to chunk_size, hard-splitting giants."""
        out: list[str] = []
        buffer = ""
        for unit in units:
            candidate = f"{buffer}{joiner}{unit}" if buffer else unit
            if len(candidate) <= self.chunk_size:
                buffer = candidate
                continue
            if buffer:
                out.append(buffer)
            if len(unit) > self.chunk_size:
                step = max(1, self.chunk_size - self.overlap)
                for i in range(0, len(unit), step):
                    out.append(unit[i:i + self.chunk_size])
                buffer = ""
            else:
                buffer = unit
        if buffer:
            out.append(buffer)
        return out
