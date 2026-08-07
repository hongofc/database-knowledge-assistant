"""Recursive character splitting with a separator hierarchy.

The idea (popularised by LangChain's RecursiveCharacterTextSplitter): try to
split on the *most semantically meaningful* boundary first, and only fall back
to a cruder one when a piece is still too large.

    heading  ->  blank line  ->  newline  ->  sentence  ->  raw characters

For a factory manual this keeps a numbered procedure or an error-code section
intact whenever it fits, instead of cutting at an arbitrary character offset.
Each chunk also records ``split_level`` so you can see *which* boundary was
used — useful evidence when comparing strategies.
"""

from __future__ import annotations

import re

from ..rag.base import Chunk, Document
from .base import HEADING_RE, PAGE_RE, SENTENCE_RE, ChunkStrategy, register


@register
class RecursiveChunker(ChunkStrategy):
    key = "recursive"
    label = "Recursive (separator hierarchy)"
    description = "Splits on heading > paragraph > line > sentence > char, cascading only when oversized."

    # Ordered coarse -> fine. Each entry: (level name, split callable).
    def _separators(self):
        return [
            ("paragraph", lambda t: t.split("\n\n")),
            ("line", lambda t: t.split("\n")),
            ("sentence", lambda t: SENTENCE_RE.split(t)),
            ("char", self._hard_window),
        ]

    def _hard_window(self, text: str) -> list[str]:
        step = max(1, self.chunk_size - self.overlap)
        return [text[i:i + self.chunk_size] for i in range(0, len(text), step)]

    def _recurse(self, text: str, level: int = 0) -> list[tuple[str, str]]:
        """Return [(piece, level_name)] where every piece fits chunk_size."""
        text = text.strip()
        if not text:
            return []
        seps = self._separators()
        if len(text) <= self.chunk_size:
            return [(text, seps[max(0, level - 1)][0] if level else "whole")]
        if level >= len(seps):
            return [(text, "char")]

        name, splitter = seps[level]
        parts = [p.strip() for p in splitter(text) if p and p.strip()]
        # This separator didn't actually divide anything — go finer.
        if len(parts) <= 1:
            return self._recurse(text, level + 1)

        # Greedily merge neighbouring parts back up to chunk_size so we don't
        # emit a flood of tiny fragments.
        out: list[tuple[str, str]] = []
        buffer = ""
        joiner = "\n\n" if name == "paragraph" else ("\n" if name == "line" else " ")
        for part in parts:
            candidate = f"{buffer}{joiner}{part}".strip() if buffer else part
            if len(candidate) <= self.chunk_size:
                buffer = candidate
                continue
            if buffer:
                out.append((buffer, name))
                tail = self._overlap_tail(buffer)
                buffer = f"{tail}{joiner}{part}".strip() if tail else part
                if len(buffer) > self.chunk_size:
                    out.extend(self._recurse(part, level + 1))
                    buffer = ""
            else:
                out.extend(self._recurse(part, level + 1))
        if buffer:
            out.append((buffer, name))
        return out

    def split(self, doc: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        cur_section = ""
        cur_page: int | None = None

        # Top of the hierarchy: cut the document at markdown headings first.
        blocks = self._split_by_heading(doc.text)
        for section, page_hint, block in blocks:
            if section:
                cur_section = section
            if page_hint is not None:
                cur_page = page_hint
            for piece, level in self._recurse(block):
                chunk = self._chunk(
                    piece, doc, cur_section, cur_page, split_level=level
                )
                if chunk:
                    chunks.append(chunk)
        return chunks

    @staticmethod
    def _split_by_heading(text: str) -> list[tuple[str, int | None, str]]:
        """Group the document into (heading, page, body) blocks."""
        blocks: list[tuple[str, int | None, str]] = []
        section = ""
        page: int | None = None
        buffer: list[str] = []

        def flush() -> None:
            body = "\n\n".join(buffer).strip()
            if body:
                blocks.append((section, page, body))

        for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
            page_match = PAGE_RE.match(para)
            if page_match:
                flush()
                buffer = []
                page = int(page_match.group(1))
                continue
            first_line = para.splitlines()[0].strip()
            heading = HEADING_RE.match(first_line)
            if heading:
                flush()
                buffer = [para]
                section = heading.group(2).strip()
                continue
            buffer.append(para)
        flush()
        return blocks
