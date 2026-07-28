# Multi-Agent Technical Compliance & Troubleshooting System
### Architecture + Tech Stack (Cost-Optimized Build Spec for Cursor)

---

## 1. Project Goal

A RAG-based multi-agent system that helps technicians/engineers by:
- Retrieving relevant info from technical manuals (**Researcher Agent**)
- Cross-checking actions/data against ISO/safety standards (**Auditor Agent**)
- Matching current issues against past repair logs (**Troubleshooter Agent**)
- Routing queries intelligently between agents (**Orchestrator**)

Domain for MVP: **Manufacturing Equipment Maintenance & Safety Compliance**

---

## 2. High-Level Architecture

```
                        ┌─────────────────────┐
                        │      User Query       │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Orchestrator Agent  │
                        │  (query classifier +  │
                        │   routing logic)      │
                        └──────────┬──────────┘
                    ┌──────────────┼──────────────┐
                    │              │               │
          ┌─────────▼───────┐ ┌────▼──────────┐ ┌─▼─────────────────┐
          │ Researcher Agent │ │ Auditor Agent  │ │ Troubleshooter     │
          │ (manuals/docs    │ │ (ISO/safety    │ │ Agent (past repair │
          │  retrieval)      │ │ cross-check)   │ │  logs similarity)  │
          └─────────┬───────┘ └────┬──────────┘ └─┬─────────────────┘
                    │              │               │
          ┌─────────▼───────┐ ┌────▼──────────┐ ┌─▼─────────────────┐
          │ Vector DB:       │ │ Vector DB:     │ │ Vector DB:         │
          │ Equipment Manuals│ │ ISO/Safety Docs│ │ Repair Logs        │
          └─────────────────┘ └───────────────┘ └────────────────────┘
                    │              │               │
                    └──────────────┼──────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │  Response Synthesizer │
                        │  (combines agent      │
                        │   outputs → 1 answer) │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Final Answer to     │
                        │   User (UI/Chat)      │
                        └─────────────────────┘
```

**Key design note:** Each agent has its **own retrieval collection** (namespace/collection inside the same vector DB instance — not 3 separate DBs). This keeps cost down while still giving each agent a clean, focused knowledge base.

---

## 3. Tech Stack (Cost-Optimized Choices)

| Layer | Choice | Why (cost/efficiency reasoning) |
|---|---|---|
| **Orchestration framework** | **LangGraph** | Free, open-source, precise control over agent routing (avoids unnecessary LLM calls = saves cost) |
| **LLM (all agents: Orchestrator, Researcher, Auditor, Troubleshooter, Synthesizer)** | **`gemini-3-flash-preview`** (Google Gemini API) | Has a **free tier in the Gemini API** — ideal for a learning/portfolio project. Even on paid usage it's cheap (~$0.25/M input, ~$1.50/M output tokens). Strong agentic/tool-use/reasoning performance for its cost, and a 1M-token context window means you rarely hit context limits even with multiple retrieved chunks. |
| **Embeddings** | **`text-embedding-004`** (Gemini API, free-tier eligible) or **local `bge-small-en-v1.5`** | Keeps everything in one API/ecosystem (simpler than mixing providers); local `bge-small` is the zero-cost fallback if you want embeddings fully offline |
| **Vector DB** | **Qdrant (self-hosted via Docker, free)** | No monthly SaaS fee (avoid Pinecone's paid tiers for a learning/portfolio project); runs fully local |
| **Backend** | **Python + FastAPI** | Lightweight, free, fast to build in Cursor |
| **Frontend** | **Streamlit** | Fastest way to get a clean demo UI without frontend overhead; free |
| **Document parsing** | **PyMuPDF (fitz)** for PDFs | Free, fast, handles manuals/ISO docs well |
| **Data storage (logs, metadata)** | **SQLite** | Zero-cost, file-based, no server needed for MVP scale |
| **Hosting (for demo)** | **Local machine** for dev; **Render free tier** or **Railway free tier** if you need a live demo link | Avoids AWS/GCP costs during learning phase |

### Total ongoing cost estimate (MVP/demo stage)
- Local/self-hosted Qdrant + SQLite → **$0 infra cost**
- Gemini free tier covers most of dev + testing + demo usage → **$0 to a few dollars total**, depending on how much you exceed free-tier rate limits during heavy testing

### Important note on `gemini-3-flash-preview`
This is a **preview model** — Google can change rate limits, pricing, or deprecate/replace it with limited notice. For a learning/portfolio project this is fine, but:
- Keep the model name in a **single config variable** (e.g. `.env` → `LLM_MODEL=gemini-3-flash-preview`), not hardcoded across files, so you can swap to a newer version (e.g. `gemini-3.1-flash-preview`) with one edit if it gets deprecated.
- Check free-tier **rate limits** (requests/minute, requests/day) before running your eval set — if you hit limits during testing, add a small retry/backoff wrapper around API calls.

---

## 4. Agent Responsibilities (Detailed)

### 4.1 Orchestrator Agent
- Input: raw user query
- Task: classify query type → route to one or more agents
- Model: `gemini-3-flash-preview` with `thinking_level: "minimal"` or `"low"` (this is a lightweight classification task, not deep reasoning — keep thinking budget low to save tokens/latency)

### 4.2 Researcher Agent
- Retrieves from: equipment manuals collection
- Task: pull relevant chunks answering "how does X work / how to do X"
- Retrieval: top-k (start with k=4), re-rank if needed later

### 4.3 Auditor Agent
- Retrieves from: ISO/safety standards collection
- Task: given proposed action/data, find matching or conflicting compliance clauses
- Output format: structured — e.g. `{clause_id, relevance, compliant: true/false, reasoning}`

### 4.4 Troubleshooter Agent
- Retrieves from: repair logs collection
- Task: semantic similarity search against past issues → return closest matches + past solutions
- Output format: `{past_case_id, similarity_score, issue, solution_applied}`

### 4.5 Response Synthesizer
- Combines outputs of whichever agents were triggered into one coherent answer
- Only invoked once per query — avoids redundant LLM calls

---

## 5. Cost-Saving Design Principles (apply these throughout)

1. **Route, don't run everything always.** Not every query needs all 3 agents — Orchestrator should only trigger relevant agents. This alone can cut LLM calls by 50-70%.
2. **Tune `thinking_level` per agent.** Since all agents use the same `gemini-3-flash-preview` model, control cost/latency via the `thinking_level` parameter instead of switching models: `minimal`/`low` for Orchestrator (routing) and Researcher (simple retrieval formatting), `medium` for Auditor and Synthesizer (need more careful reasoning over compliance clauses), `high` only if eval results show Auditor accuracy needs it.
3. **Use context caching.** Gemini 3 supports automatic context caching — if your ISO docs / manuals don't change often, this reduces repeated input-token cost across queries.
4. **Local embeddings as a free fallback.** If you want zero embedding cost even beyond the Gemini free tier, use local `bge-small` model via `sentence-transformers` instead of `text-embedding-004`.
5. **Cache repeated queries.** Simple dict/SQLite cache for identical or near-identical queries during testing — avoids re-calling the API for the same eval question repeatedly.
6. **Self-hosted vector DB.** Qdrant/Chroma locally = no monthly SaaS fee, unlike Pinecone/Weaviate Cloud.
7. **Batch embed documents once**, not per-query — embed your manuals/ISO docs/logs one time during setup, not on each request.
8. **Limit context window sent to LLM.** Only send top-k retrieved chunks (not entire documents) to keep token usage — and cost — low, even though Gemini's 1M context window means you technically *could* send more.

---

## 6. Suggested Folder Structure (for Cursor)

```
compliance-troubleshoot-system/
├── data/
│   ├── manuals/              # equipment manual PDFs
│   ├── iso_standards/        # ISO/safety doc PDFs
│   └── repair_logs/          # synthetic repair log data (json/csv)
├── ingestion/
│   ├── parse_docs.py         # PDF → text chunks
│   ├── embed_and_store.py    # embeddings → Qdrant collections
├── agents/
│   ├── orchestrator.py
│   ├── researcher_agent.py
│   ├── auditor_agent.py
│   ├── troubleshooter_agent.py
│   └── synthesizer.py
├── vectorstore/
│   └── qdrant_client.py
├── eval/
│   ├── test_queries.json     # ground-truth eval set
│   └── run_eval.py
├── app/
│   └── streamlit_app.py      # demo UI
├── requirements.txt
├── .env                       # API keys (never commit this)
└── README.md
```

---

## 7. Build Order (matches earlier roadmap)

1. Ingestion pipeline (parse + chunk + embed + store) — test retrieval manually
2. Single working agent (Researcher only) end-to-end
3. Add Auditor agent + its collection
4. Add Troubleshooter agent + its collection
5. Build Orchestrator routing logic
6. Build Synthesizer
7. Wrap in Streamlit UI
8. Build eval set (20-25 queries) and test/tune
9. Record demo, write README, publish

---

## 8. Notes for Cursor Development

- Keep `.env` for your Gemini API key (`GOOGLE_API_KEY` or `GEMINI_API_KEY`) and model name (`LLM_MODEL=gemini-3-flash-preview`) — never hardcode either
- Use Cursor's inline chat to scaffold each agent file one at a time — don't ask it to generate the whole system in one go, it'll produce inconsistent code
- Test ingestion + retrieval thoroughly before touching agent logic — most bugs in RAG systems come from bad chunking/retrieval, not from the LLM
- Keep prompts in separate files (`prompts/`) so you can iterate without touching agent logic code
