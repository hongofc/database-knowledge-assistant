"""Fill the AIMP A1 poster template with Group 1's measured content.

The template is built from DrawingML text boxes and Word fragments every
heading letter-by-letter, so edits happen at PARAGRAPH level: join the runs,
match the placeholder, then write the replacement into the first run and blank
the rest (which keeps the first run's font, size and colour).

Every panel exists TWICE in the package (Word's AlternateContent fallback), so
replacements are applied to every matching paragraph, not just the first.

Run:
    .pdfvenv/Scripts/python.exe scripts/fill_poster.py \
        poster_template.docx AIMP_Poster_Group1_FILLED.docx
"""
from __future__ import annotations

import re
import sys

from docx import Document

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# --- content -----------------------------------------------------------------
# Numbers here are MEASURED (see poster_evidence.json). Estimates say so.

ONE_LINE = (
    "Ask factory documents and database telemetry in plain English \u2014 "
    "it cites its sources or refuses."
)

BEFORE = (
    "A line goes down at 2am. The technician scrolls a 40-page PDF on a shared "
    "drive hunting one alarm code. The DBA exports a spreadsheet and pivots it "
    "by hand. Both end up phoning someone who already went home."
)

CHANGED_BEFORE = (
    "Open the manual, scroll, hope it is the right PDF. For telemetry, export "
    "to Excel and pivot by hand.  (estimated \u2014 we never timed it)"
)

CHANGED_AFTER = (
    "3.7 s median, with the exact file and section cited. Telemetry: one "
    "sentence in, one sentence out, SQL shown.  (measured, n=7)"
)

CHANGED_NOTE = "16 documents + 2,372 telemetry rows \u2192 one question box."

CHANGED_CAVEAT = (
    "Answered 7/8 in-corpus questions; refused 4/4 out-of-corpus. "
    "The \u201cbefore\u201d times are estimates."
)

BUILT_CAPTION = (
    "A router sends each question to three document specialists or a SQL "
    "engine. Chunks below a measured score floor are dropped before the model "
    "answers."
)

LEARNED = (
    "We assumed the abstain threshold belonged to our app. It belongs to the "
    "embedding model. When Ollama dropped off this machine and OpenAI "
    "embeddings took over, the same correct document scored 0.637 against a "
    "0.68 floor \u2014 so the app refused a question it had answered the day "
    "before."
)

BUILT_WITH = (
    "Python \u00b7 Streamlit \u00b7 ChromaDB \u00b7 OpenAI gpt-4o-mini + "
    "text-embedding-3-small \u00b7 Ollama / LM Studio \u00b7 SQLite \u00b7 "
    "pytest \u00b7 Docker \u00b7 GitHub"
)

TITLE = "Database Knowledge Assistant"

# placeholder (normalised, lowercase) -> replacement
RULES: list[tuple[str, str]] = [
    ("one line: what it does, for whom. fifteen words maximum.", ONE_LINE),
    ("rag-based prototype", TITLE),
    ("the manual process, in human terms.", BEFORE),
    ("how long did this take before?", CHANGED_BEFORE),
    ("how long does it take now?", CHANGED_AFTER),
    ("not a time saving? a different kind of change is fine:", CHANGED_NOTE),
    ("one question\u201d.estimated? say so.", CHANGED_CAVEAT),
    ("[25 words of explanation beneath the diagram]", BUILT_CAPTION),
    ("one architecture diagram.", ""),
    ("show how a question flows through the system", ""),
    ("a specific finding, not a general lesson.", LEARNED),
    ("than it saved.[50 words]", ""),
    ("answer one question: what did you expect that turned out differently?", ""),
    ("what tool?", BUILT_WITH),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def para_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(f"{W}t"))


def content_paragraphs(doc):
    """Paragraphs that hold text, including those inside drawing text boxes."""
    for p in doc.element.body.iter(f"{W}p"):
        if p.find(f".//{W}txbxContent") is not None:
            continue  # wrapper around a text box; the inner paragraphs come separately
        yield p


def set_paragraph_text(p, text: str) -> None:
    """Write `text` into the paragraph's first run; blank every other run.

    Keeps the first run's formatting, which is what the template's styling
    lives on. Removing the runs outright would drop the paragraph properties.
    """
    t_nodes = list(p.iter(f"{W}t"))
    if not t_nodes:
        return
    t_nodes[0].text = text
    # preserve leading/trailing spaces Word would otherwise collapse
    t_nodes[0].set(
        "{http://www.w3.org/XML/1998/namespace}space", "preserve"
    )
    for t in t_nodes[1:]:
        t.text = ""


def main(src: str, dst: str) -> None:
    doc = Document(src)
    applied: dict[str, int] = {key: 0 for key, _ in RULES}

    for p in content_paragraphs(doc):
        txt = norm(para_text(p))
        if not txt:
            continue
        for key, replacement in RULES:
            if key in txt:
                set_paragraph_text(p, replacement)
                applied[key] += 1
                break

    doc.save(dst)

    print(f"saved {dst}\n")
    missed = []
    for key, _ in RULES:
        n = applied[key]
        flag = "ok " if n else "MISS"
        print(f"  [{flag}] x{n}  {key[:62]}")
        if not n:
            missed.append(key)
    if missed:
        print(f"\n{len(missed)} placeholder(s) NOT found - check the template.")
        sys.exit(1)
    print("\nall placeholders replaced")


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "poster_template.docx"
    b = sys.argv[2] if len(sys.argv) > 2 else "AIMP_Poster_Group1_FILLED.docx"
    main(a, b)
