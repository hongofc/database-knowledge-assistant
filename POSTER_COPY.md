# Poster copy — AIMP Group 1

Every number below was measured on 2026-10-19 against the running app.
Source data: `poster_evidence.json`. Estimates are labelled as estimates.

---

## TITLE

**Database Knowledge Assistant**

## ONE LINE (15 words max)

> Ask factory documents and database telemetry in plain English — it cites its
> sources or refuses.

*(14 words)*

---

## THE BEFORE (40 words)

> A line goes down at 2am. The technician scrolls a 40-page PDF on a shared
> drive hunting one alarm code. The DBA exports a spreadsheet and pivots it by
> hand. Both end up phoning someone who already went home.

*(39 words)*

---

## WHAT CHANGED — BEFORE → AFTER

| | Before | After |
|---|---|---|
| Find an alarm code | Open the manual, scroll, hope you picked the right PDF *(estimated — not timed)* | **3.7 s median**, answer + the exact file and section *(measured, n=7)* |
| Telemetry question | Export to Excel, pivot by hand *(estimated)* | One sentence in, one sentence out — with the SQL shown *(measured)* |
| Where the answer lives | 16 documents + a 2,372-row spreadsheet | One question box |
| When the answer is not there | You keep looking, or you guess | **Refuses — 4/4 out-of-corpus questions** *(measured)* |

**Honest framing for the panel:**
> 200 pages and 2,372 telemetry rows → one question.
> Answer latency 2.5–5.1 s (median 3.7 s, measured).
> The "before" times are estimates — we never stopwatched the manual process.

---

## WHAT WE BUILT — caption beneath the diagram (25 words)

> A router sends each question to three document specialists or a SQL engine.
> Chunks below a measured score floor are dropped before the model answers.

*(25 words)*

Diagram file: `poster_architecture.pptx` → export slide 1 as PNG.

---

## WHAT WE LEARNED (50 words)

**The question it answers: what did you expect that turned out differently?**

> We assumed the abstain threshold belonged to our app. It belongs to the
> embedding model. When Ollama dropped off this machine and OpenAI embeddings
> took over, the same correct document scored 0.637 against a 0.68 floor — so
> the app refused a question it had answered the day before.

*(50 words)*

**Backup findings if a reviewer pushes** (all measured, all unflattering):

- Hybrid retrieval (BM25 + vector, RRF) scored **MRR 0.88 — worse** than plain
  vector at **0.93**. We kept vector and reported the result rather than hiding it.
- Grounded and adversarial scores **overlap**: grounded 0.4725–0.7857,
  adversarial 0.0994–0.5575. No threshold is clean. A fake alarm code `Z-999`
  scores **0.5575** against a 0.60 floor — a 0.043 margin.
- We still have **one false abstention**: *"What are the changeover steps
  between product variants?"* scores 0.4725 and gets refused, even though
  `changeover_sop.md` contains a section called *"Changeover steps"*. Lexical
  overlap is high; embedding similarity is not. We would rather refuse than
  invent, but this is the cost.

---

## BUILT WITH

**Language / UI** Python 3.11 · Streamlit
**Retrieval** ChromaDB · BM25 (rank-bm25) · reciprocal-rank fusion
**Embeddings** OpenAI `text-embedding-3-small` · Ollama `nomic-embed-text` · offline hash fallback
**Models** OpenAI `gpt-4o-mini` · GitHub Copilot · Anthropic · Ollama / LM Studio (local)
**Telemetry** SQLite · openpyxl · schema-constrained text-to-SQL
**Quality** pytest (44 deterministic SQL tests) · 17-case golden set · MRR / Hit@k harness
**Delivery** Docker · GitHub — github.com/hongofc/database-knowledge-assistant

---

## TEAM — Group 1

| Name | Suggested panel line |
|---|---|
| Sylvia Wong Shiau Ching | *(to fill)* |
| Chin Ee Mei | *(to fill)* |
| Khoo Yeong Kang | *(to fill)* |
| Muhammad Muzzammil Bin Mohd Salahudin | *(to fill)* |
| Phuah Hong | *(to fill)* |

Left blank deliberately — assignments should come from the team, not from me.

---

## Evidence appendix (not for the poster — for questions)

```
retriever       vector
embedding       text-embedding-3-small
chunk strategy  metadata_aware
abstain floor   0.60
chunks indexed  maintenance 55 · safety 51 · quality 47  (153 total)
cold index      56.7 s  (re-runs on every restart - .chroma does not persist)

answered when it should    7/8
abstained when it should   4/4
answer latency             min 2.5s · median 3.7s · max 5.1s
grounded top-score range   0.4725 – 0.7857
adversarial top-score      0.0994 – 0.5575
cleanly separable          False
```

Worked examples with citations:

- *alarm code E-204* → "Spindle overload on the VMX-500"
  → `data/maintenance/error_code_reference.md > Quick lookup table`
- *PPE in the grinding area* → face shield + glasses, earplugs, cut-resistant gloves
  → `data/safety/ppe_requirements.md > 2. PPE matrix`
- *lockout tagout steps* → `data/safety/lockout_tagout_sop.md > 3. The 6 steps`
- *preventive maintenance schedule* → `preventive_maintenance_schedule.pdf (p.1)`
  — note this one is a **PDF**, proving the ingest pipeline handles binaries
- *top 5 wait types* → text-to-SQL returns counts with the SQL shown
