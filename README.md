# Database Knowledge Assistant

Grounded answers over **database telemetry and operational documentation** —
with citations, verifiable SQL, and the honesty to refuse when the answer
isn't there.

### What we added

The Capstone Level 2 kit answers documentation questions with RAG. We kept that
as the baseline and built a **second engine on top of it**: a text-to-SQL agent
over real SQL Server session telemetry, contributed and specified by a DBA-team
member on this project.

That extension is the point of this build. A DBA's questions —
*"which database burned the most CPU?"*, *"which session blocks others most
often?"* — cannot be answered by retrieval at all. No document contains the
answer; it has to be **computed** across 2,372 rows. Bolting a SQL engine onto a
RAG system, and routing each question to the tool that can actually answer it,
is what took this from a documentation chatbot to something a DBA would use.

Everything else — provider routing, the evaluation harness, session memory,
the branded UI — was built to support those two engines.

### Two kinds of question, two engines

| Question | Engine | Why |
|---|---|---|
| *"What does alarm code E-204 mean?"* | **RAG** over official docs | The answer is written down; quote it with a citation |
| *"Which database used the most CPU?"* | **Text-to-SQL** over telemetry | The answer must be *computed* over 2,372 rows — retrieval cannot SUM |

Both refuse to guess. RAG abstains when no document scores above a measured
trust floor; SQL answers ship the query used, so any number can be re-run and
checked.

---

## Quick start

```bash
# 1. Create the virtual environment (Python 3.11)
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# 2. Launch
bash run_app.sh                # macOS / Linux / Git Bash
run_app.bat                    # Windows CMD
```

Open <http://localhost:8501>.

> **Important:** always launch through `run_app.sh` / `run_app.bat`, or with
> `.venv/Scripts/python.exe -m streamlit run app.py`.
> A bare `streamlit run app.py` resolves to the *system* Python, which does not
> have `chromadb` installed — the app then silently falls back to the keyword
> retriever. The launcher also refuses to start a second server on a port that
> is already in use, which otherwise produces two servers on one port and very
> confusing behaviour.

### No API key required

The app runs fully offline against a local model:

```bash
ollama serve && ollama pull qwen2.5:3b && ollama pull nomic-embed-text
```

Cloud providers (OpenAI, Anthropic, GitHub Copilot) are optional. Keys are
entered **in the sidebar**, kept in-process, and never written to disk.
GitHub Copilot uses browser device-flow sign-in.

---

## Features delivered

### Retrieval-augmented generation with abstention
Three specialists — **Maintenance & Troubleshooting**, **Safety & Compliance**,
**Quality & Operations** — each with an isolated vector collection. A router
picks the specialist per question. Every answer carries citations back to the
source document.

The guardrail is deterministic and runs *before* the LLM is called, so the
model is never given the chance to invent an answer:

```python
trusted = [h for h in hits if h.score >= self.cfg.min_score]
if not trusted:
    return abstain()
```

### Four chunking strategies, measured not assumed
`simple` (fixed), `recursive`, `semantic`, and `metadata_aware` — selectable in
the UI, and benchmarked against a 17-case golden set (`eval/golden_set.yaml`):

| Strategy | Chunks | MRR | Hit@5 |
|---|---|---|---|
| fixed | 60 | 0.92 | 1.00 |
| recursive | 108 | 0.88 | 1.00 |
| **metadata_aware** | 153 | **0.93** | 1.00 |

Retriever comparison on the same set: **vector 0.93**, keyword/BM25 0.70,
hybrid RRF 0.88. Hybrid measured *worse* than pure vector here — reported as
found rather than quietly dropped.

```bash
.venv/Scripts/python.exe eval/run_eval.py
```

### Text-to-SQL telemetry agent
Natural-language questions over `data/dba/db_session.xlsx` (2,372 rows × 15
columns) loaded into an in-memory SQLite snapshot. Read-only whitelist, and
every answer shows its SQL.

```bash
.venv/Scripts/python.exe -m dba "which database used the most CPU?"
.venv/Scripts/python.exe -m dba --schema        # inspect the table
.venv/Scripts/python.exe -m dba --sql "SELECT ..."   # run raw SQL
```

### Multi-provider LLM routing
Ollama, LM Studio, OpenAI, Anthropic, GitHub Copilot. Model lists are fetched
**live** from each provider, so the picker shows exactly what your account is
entitled to — a hardcoded list silently breaks when an entitlement differs.
Every reply is captioned with the provider *and* model that produced it, so a
failure is attributable to a specific model rather than "the provider".

### Persistent sessions
Conversations stored in SQLite with full history, citations, and per-message
provider/model metadata. Resume, delete, or clear all from the sidebar.

---

## Categories met

| # | Category | Where |
|---|---|---|
| 1 | Working Prototype | Streamlit app, live demo |
| 2 | RAG | ChromaDB, citations, abstention |
| 3 | Advanced Chunking | 4 strategies, benchmarked |
| 5 | Memory | SQLite sessions + conversation history |
| 6 | Tool Use | Text-to-SQL over the telemetry workbook |
| 8 | Local LLM | Ollama + LM Studio, hybrid routing |
| 10 | Multiple Data Sources | 16 documents across 3 corpora + XLSX |
| 12 | Evaluation | 17-case golden set, MRR / Hit@k |
| 13 | Deployment | Dockerfile, launchers, public GitHub repo |

**9 categories** against a minimum of 5.

Category 9 (Data Pipeline) is arguable — `factory_knowledge/ingest.py` does
parse and clean PDF/DOCX/Markdown sources — but it is left unclaimed as
fairly standard document loading rather than a distinct pipeline.

### Not claimed
This is a **router + RAG + text-to-SQL** system, not a multi-agent one. There
is no LangGraph, no planning loop, no cyclic state graph, and no tool that
takes an action in the world. The router selects a persona; it does not plan.
Category 4 (Agent / LangGraph) is deliberately **not** claimed.

---

## Testing

```bash
.venv/Scripts/python.exe tests/test_smoke.py          # 8/8
.venv/Scripts/python.exe tests/test_dba.py            # 44/44, no LLM needed
.venv/Scripts/python.exe tests/test_dba.py --llm --provider openai   # 46/46
```

The DBA suite is two-layered. The deterministic tests run in ~1s with no LLM
and cover the SQL guard, schema, and known-answer aggregates. The `--llm` layer
tests actual SQL generation and asserts on the **answer, not the SQL text** —
two valid queries can differ in wording but agree on the number.

A finding worth recording: `qwen2.5:3b` scores 45/46, failing one question by
inventing a `WHERE status='running'` filter. It picked the right database but
returned 28,605,652 instead of 60,214,551. Small local models are weak at
text-to-SQL; OpenAI is recommended for the SQL path, local models for RAG.

---

## Configuration

Copy `.env.example` to `.env`. Useful settings:

| Variable | Default | Notes |
|---|---|---|
| `RETRIEVER` | `keyword` | `keyword`, `vector`, or `hybrid` |
| `CHUNK_STRATEGY` | `simple` | `metadata_aware` scored best |
| `MIN_SCORE` | *(auto)* | Blank picks a floor matched to the retriever's scale |
| `TOP_K` | `5` | Chunks retrieved per question |

`MIN_SCORE` defaults are scale-specific — **4.0** for BM25 (unbounded, ~0-16
here) and **0.68** for cosine (0-1). A single fixed number cannot serve both:
0.68 on BM25 would filter nothing at all.

Changing the chunking strategy or retriever triggers a **~90 second re-index**.
Do not change them mid-demo.

---

## Project layout

```
app.py                  Streamlit UI
ui_helpers.py           Provider wiring, caching, session helpers
cli.py                  Terminal interface
factory_knowledge/
  agent.py              Grounding guardrail + prompt construction
  providers.py          6 LLM providers, live model discovery
  chunking/             simple, recursive, semantic, metadata_aware
  rag/                  keyword (BM25), vector (Chroma), hybrid (RRF)
  sessions.py           SQLite persistence
dba/                    Text-to-SQL agent (separate package)
eval/                   Golden set + benchmark harness
tests/                  Smoke + DBA suites
scripts/make_logo.py    Regenerate the sidebar wordmark
```

---

## Team contributions

> **Draft — confirm before submitting.** The feature areas below are the real
> work items in this repo, but the assignment of who did what must be set by
> the team. Every member must have at least one feature.

| Member | Contribution |
|---|---|
|Sylvia Wong Shiau Ching|*Working prototype, RAG*|
|Chin Ee Mei|*Evaluation*|
|Khoo Yeong Kang|*Tool use, Deployment*|
|Muhammad Muzzammil Bin Mohd Salahudin|*Memory , Multiple data sources*|
|Phuah Hong|*Advanced Chunking, Local LLM*|

### Feature areas available to assign

Pick from these — every item is real, demonstrable work in this repo. Whoever
takes an area should be able to open the listed files and explain them, since
individual contributions must be presented on demo day.

- **RAG core & grounding guardrail** — `factory_knowledge/agent.py`
  - Retrieval, citation building, and the deterministic abstention that runs
    *before* the LLM is called (`score >= min_score`, else refuse)
  - Demo: ask about alarm code `Z-999` and watch it refuse
  - *Covers category 2*

- **Chunking strategies** — `factory_knowledge/chunking/`
  - Four interchangeable strategies: `simple`, `recursive`, `semantic`,
    `metadata_aware`
  - Demo: switch strategy in the sidebar and compare answers
  - *Covers category 3*

- **Retrievers** — `factory_knowledge/rag/`
  - BM25 keyword, Chroma vector, and hybrid RRF behind one interface
  - Includes the scale-specific abstain floors (4.0 for BM25, 0.68 for cosine)
  - *Supports category 2*

- **Evaluation harness** — `eval/`
  - 17-case golden set, MRR and Hit@k across all strategy/retriever pairs
  - Produced the finding that hybrid RRF scores *worse* than pure vector
  - Demo: `.venv/Scripts/python.exe eval/run_eval.py`
  - *Covers category 12*

- **Text-to-SQL telemetry agent** — `dba/`
  - Natural language to SQL over 2,372 rows, read-only whitelist, shows its SQL
  - Demo: `.venv/Scripts/python.exe -m dba "which database used the most CPU?"`
  - *Covers categories 6 and 10*

- **Multi-provider LLM routing** — `factory_knowledge/providers.py`
  - Six providers (Ollama, LM Studio, OpenAI, Anthropic, Copilot, retrieval-only)
  - Live model discovery from each provider's API, GitHub device-flow login,
    embedding-model filtering
  - *Covers category 8*

- **Streamlit UI & branding** — `app.py`, `.streamlit/config.toml`
  - ams OSRAM theme (`#FD5000`, sampled from the logo), two-phase turn
    rendering, in-UI API key entry, per-reply provider/model attribution
  - *Covers category 1*

- **Session persistence & memory** — `factory_knowledge/sessions.py`
  - SQLite chat history with citations and per-message metadata; the last six
    turns are fed back into the prompt so follow-up questions work
  - *Covers category 5*

- **Test suites** — `tests/`
  - Smoke suite (8 checks) plus a two-layer DBA suite: 44 deterministic tests
    with no LLM, 46 end-to-end with one
  - *Supports category 12*

- **Deployment & packaging** — `Dockerfile`, `run_app.sh`, `run_app.bat`
  - Container build, cross-platform launchers, port-collision guard, public
    GitHub repository
  - *Covers category 13*

---

## Known limitations

- Embeddings cannot distinguish near-identical codes: a plausible-but-fake code
  like `Z-999` scores similarly to a real `E-204`. The prompt-level guardrail is
  the backstop, and it is not perfect.
- Grounded and adversarial score ranges **overlap** (cosine 0.643-0.847 vs
  0.50-0.673), so any abstain floor trades false-abstains against
  false-answers. There is no threshold that separates them cleanly.
- The corpus is 16 fictional documents written for this exercise, not real
  factory documentation.
- API keys live in process memory only; restarting the server clears them.
