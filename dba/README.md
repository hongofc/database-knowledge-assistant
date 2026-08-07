# DBA Session Telemetry — Text-to-SQL

Answers questions about `data/dba/db_session.xlsx` (2,372 rows of SQL Server
session monitoring data) by **generating SQL**, not by retrieving text.

## Why not RAG?

The factory corpus is prose, so embeddings work: meaning lives in the words.
This workbook is numeric telemetry, where meaning lives in *aggregation*.

> "Which database used the most CPU?"

Answering that requires summing `CPU` across all 2,372 rows. Retrieval returns
the ~5 rows that look most textually similar — never the correct total, and it
returns them **confidently**. Embeddings also cannot compare magnitudes:
`60214551` and `344` both just look like "a number".

So the split is:

| Data | Tool | Rationale |
|------|------|-----------|
| Manuals, SOPs (`data/maintenance`, `safety`, `quality`) | RAG | meaning is in words |
| Session telemetry (`data/dba/*.xlsx`) | Text-to-SQL | meaning is in aggregation |

## How it works

```
question -> LLM writes SELECT -> SQLite computes -> LLM explains the rows
```

The **numbers always come from the database**, never from the model. The LLM
only translates the question and narrates the result — the two things it is
genuinely good at. Every answer ships with the SQL that produced it, so any
claim can be re-run and checked.

## Usage

Command line:

```bash
python -m dba --schema
python -m dba "which database used the most CPU?"
python -m dba "which sessions are blocking others, and how often?"
python -m dba --sql "SELECT status, COUNT(*) FROM db_sessions GROUP BY 1"
python -m dba --provider openai "top 3 wait types"
```

Python:

```python
from dba import DBAAgent

answer = DBAAgent().ask("Which database used the most CPU?")
print(answer.sql)     # the generated SELECT
print(answer.rows)    # [('db06', 60214551)]
print(answer.text)    # plain-language explanation
```

In the Streamlit app: just ask a database question. `is_dba_question()` routes
it here automatically; the answer shows a "🔎 SQL and result" panel.

## Safety

`run_query()` is a **whitelist**: only `SELECT`/`WITH` run. `INSERT`, `UPDATE`,
`DELETE`, `DROP`, `ALTER`, `ATTACH`, `PRAGMA` and multi-statement input are all
rejected. The workbook is copied into an **in-memory** SQLite database, so the
source file is never modified.

This matters: an LLM generating SQL against a live production database is a real
risk. Point this at an exported snapshot, never at prod.

## Testing

Two layers, because they answer different questions.

**Layer 1 — deterministic (no LLM, ~1s).** Run on every commit:

```bash
.venv/Scripts/python.exe tests/test_dba.py     # 44/44
```

Covers loading (2,372 rows, 15 columns), numeric typing, the safety guard
(9 attacks blocked, 5 legitimate queries allowed), SQL cleanup, routing
(9 questions, 0 misroutes) and known ground-truth answers.

**Layer 2 — the LLM writing SQL (slow, non-deterministic).** Opt in:

```bash
.venv/Scripts/python.exe tests/test_dba.py --llm --provider openai
```

This asserts on the **answer**, not the SQL text — two different-but-valid
queries can both be correct, so comparing SQL strings would fail for no reason.
Ground truth comes from hand-written SQL in layer 1.

| Provider | Result |
|---|---|
| `openai` (gpt-4o-mini) | **46/46** |
| `ollama` (qwen2.5:3b) | **45/46** — right database, wrong total |

## Measured limitation

Text-to-SQL is much harder than chat, and small models fail at it:

| Model | Generated SQL | Result |
|-------|---------------|--------|
| `qwen2.5:3b` (local) | invented `WHERE status='running'` | ❌ wrong database |
| `qwen2.5:3b` (local) | invented a `PAGEIOLATCH_SH` filter | ❌ all zeros, then confidently rationalised it |
| `gpt-4o-mini` (API) | `SELECT database_name, SUM(CPU) ... ORDER BY ... DESC` | ✅ `db06`, 60,214,551 |

`DBAAgent` therefore prefers the strongest reachable provider by default. This
is the one place in the project where a local-only setup measurably underperforms —
worth stating plainly rather than hiding.

A second measured pitfall: `LIMIT` without `ORDER BY` returns *arbitrary* rows.
The first version reported session `52` blocking once, when the real answer was
session `114` blocking 14 times. The prompt now mandates an explicit `ORDER BY`.

## Findings in this dataset

- **`db06` dominates CPU**: 60,214,551 ms across 1,242 sessions — ~31× every
  other database combined. The obvious first thing a DBA should investigate.
- **Session 114 is the top head blocker**, blocking 14 times.
- **`PAGEIOLATCH_SH` is the most common wait** (223 occurrences), which points at
  disk I/O latency rather than CPU contention.
