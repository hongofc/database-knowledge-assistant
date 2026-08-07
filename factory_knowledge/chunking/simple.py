"""Baseline: fixed-size character chunking.

This reproduces the original kit behaviour on purpose. It is the *control*
in the evaluation harness — every advanced strategy must beat it on real
numbers, or it isn't worth the complexity.

Weakness it demonstrates: boundaries fall at a character count, so a table row
can be severed from its header and a procedure step from its warning.
"""

from __future__ import annotations

from ..rag.base import Chunk, Document
from .base import HEADING_RE, PAGE_RE, ChunkStrategy, register


@register
class FixedChunker(ChunkStrategy):
    key = "fixed"
    label = "Fixed-size (baseline)"
    description = "Fixed character windows on paragraph boundaries, with overlap."

    def split(self, doc: Document) -> list[Chunk]:
        paragraphs = [p.strip() for p in doc.text.split("\n\n") if p.strip()]
        chunks: list[Chunk] = []
        buffer = ""
        buf_section = ""
        buf_page: int | None = None
        cur_section = ""
        cur_page: int | None = None

        def emit(text: str, section: str, page: int | None) -> None:
            chunk = self._chunk(text, doc, section, page)
            if chunk:
                chunks.append(chunk)

        for para in paragraphs:
            page_match = PAGE_RE.match(para)
            if page_match:
                emit(buffer, buf_section, buf_page)
                buffer = ""
                cur_page = int(page_match.group(1))
                continue

            heading = HEADING_RE.match(para.splitlines()[0].strip())
            if heading:
                cur_section = heading.group(2).strip()

            if not buffer:
                buf_section, buf_page = cur_section, cur_page

            if len(buffer) + len(para) + 2 <= self.chunk_size:
                buffer = f"{buffer}\n\n{para}".strip()
                continue

            emit(buffer, buf_section, buf_page)
            if len(para) <= self.chunk_size:
                tail = self._overlap_tail(buffer)
                buffer = f"{tail}\n\n{para}".strip() if tail else para
                buf_section, buf_page = cur_section, cur_page
            else:
                start = 0
                while start < len(para):
                    emit(para[start:start + self.chunk_size], cur_section, cur_page)
                    start += self.chunk_size - self.overlap
                buffer = ""

        emit(buffer, buf_section, buf_page)
        return chunks
