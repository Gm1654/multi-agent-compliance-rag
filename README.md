# Multi-Agent Compliance & Troubleshooting RAG System

A multi-agent Retrieval-Augmented Generation (RAG) system for hydraulic press maintenance, safety compliance auditing, and fault troubleshooting, powered by **Google Gemini 3.1 Flash Lite** and **Qdrant Cloud**.

---

## 📌 Project Overview

Industrial hydraulic equipment maintenance requires balancing strict safety compliance, operating limits, and historical repair knowledge. This system employs an **Orchestrator-Specialist Architecture** to route incoming technician queries to specialized domain agents:

- **Researcher Agent**: Queries equipment operating manuals (`equipment_manuals` Qdrant collection) for step-by-step procedures, specifications, and limits.
- **Auditor Agent**: Queries safety regulations and job safety analysis docs (`compliance_docs` Qdrant collection) to issue safety rulings.
- **Troubleshooter Agent**: Queries maintenance logs (`repair_logs` Qdrant collection) for matching past repair case IDs (`RL-2024-*`, `RL-2025-*`).
- **Synthesizer**: Merges agent outputs into a unified, safety-first response.

---

## 🏗️ System Architecture

For detailed architectural diagrams, data flows, collection schemas, and agent prompt specs, see [ARCHITECTURE.md](ARCHITECTURE.md).

```
User Query
    │
    ▼
[Orchestrator Agent] ─── (Classifies query & selects minimal necessary agents)
    │
    ├──► [Researcher Agent]      ──► Qdrant: equipment_manuals
    ├──► [Auditor Agent]         ──► Qdrant: compliance_docs
    └──► [Troubleshooter Agent]  ──► Qdrant: repair_logs
    │
    ▼
[Synthesizer] ──► Final Citation-Backed Technician Response
```

---

## 📊 Evaluation & Benchmark Results

The system was evaluated against a ground-truth benchmark suite of 32 verified test queries plus 10 unseen holdout queries across 4 categories:

- **Overall Routing Accuracy**: **100.0% (42/42 queries matched)**
  - **Tuning Benchmark Set (32 queries)**: 100.0% (32/32)
  - **Unseen Holdout Set (10 queries)**: 100.0% (10/10)
- **Category Breakdown**:
  - `researcher` (8/8) — 100%
  - `auditor` (7/7) — 100%
  - `troubleshooter` (13/13) — 100%
  - `multi_agent` (4/4) — 100%
  - `holdout` (10/10) — 100%
- **Answer Quality**: Manually verified against ground-truth notes for complete procedural accuracy, citation of real PDF page numbers, and strict adherence to safety compliance warnings.

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Qdrant Cloud account & cluster
- Google Gemini API key

### 2. Environment Setup
Clone the repository and install dependencies:

```bash
git clone https://github.com/Gm1654/multi-agent-compliance-rag.git
cd multi-agent-compliance-rag
pip install -r requirements.txt
```

Create your `.env` file from the example template:

```bash
cp .env.example .env
```

Update `.env` with your credentials:
```ini
QDRANT_URL=https://your-qdrant-cluster-url.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here
GOOGLE_API_KEY=your_google_gemini_api_key_here
LLM_MODEL=gemini-3.1-flash-lite
```

### 3. Running the App & Evaluation

**Streamlit Web Interface**:
```bash
streamlit run app/main.py
```

**Run Automated Routing Evaluation**:
```bash
# Run full 32-query benchmark
python eval/run_eval.py --output eval/eval_results_final.csv --delay 2

# Run unseen holdout eval
python eval/run_eval.py --queries eval/test_queries_holdout.json --output eval/eval_results_holdout.csv --delay 2
```

---

## 📁 Repository Structure

```
├── agents/                  # Specialist & Orchestrator agent definitions
├── app/                     # Streamlit UI implementation
├── data/                    # Document excerpts & ingested corpus references
├── eval/                    # Benchmark JSONs, holdout sets, and eval scripts
├── ingestion/               # PDF chunking & Qdrant vectorstore ingestion scripts
├── vectorstore/             # Vector database connection utilities
├── ARCHITECTURE.md          # Full technical design specification
├── README.md                # Project documentation
└── requirements.txt         # Dependencies
```
