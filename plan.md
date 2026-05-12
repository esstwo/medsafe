# MedSafe — Implementation Plan

**Project:** FDA Drug Interaction & Safety Advisor  
**Stack:** Python (FastAPI) backend · React frontend · MCP server (Claude plugin)  
**Timeline:** 6 weeks  
**Date drafted:** 2026-05-11

---

## 1. What We're Building

MedSafe is an AI-powered drug interaction and safety advisor. A patient enters their complete medication list (prescriptions, OTC drugs, supplements) in plain English. The system normalizes those drugs, checks every pairwise combination for known interactions, retrieves real FDA adverse event data, attributes reported symptoms to possible drug causes, and generates a plain-language safety briefing with full source citations.

MedSafe ships as **two interfaces over one shared core**:
- **React web app** — standalone web UI backed by a FastAPI REST API
- **MCP server** — a Claude plugin usable directly inside Claude Desktop or claude.ai, exposing the same tools so Claude acts as the conversational UI

**Core constraint:** MedSafe is an informational tool. It never recommends starting, stopping, or changing medications. Every factual claim must trace to a cited source (FDA label, DrugBank, FAERS). Uncertainty must always be stated explicitly.

---

## 2. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Claude claude-sonnet-4-6 (Anthropic) | Strong tool-calling, reliable structured output, cost-effective for multi-step pipelines |
| Backend framework | FastAPI (Python 3.12) | Async for concurrent external API calls, Pydantic for typed schemas |
| Frontend | React 18 + TypeScript + Vite | Polished UI, component reuse, better than Streamlit for production feel |
| UI components | shadcn/ui + Tailwind CSS | Fast to build clean clinical-feeling UI |
| Embedding model | `text-embedding-3-small` (OpenAI) | Cost-efficient; good retrieval quality for medical text |
| Vector store | ChromaDB (local dev) → Pinecone (demo) | Zero-cost local dev; Pinecone for serverless demo |
| Database | SQLite (dev) → PostgreSQL (prod) | DrugBank structured records; session state |
| External APIs | RxNorm (NLM), openFDA FAERS, DailyMed | All public domain, no auth required for MVP |
| Observability | LangSmith | Trace every orchestrator step |
| MCP framework | `mcp` Python SDK (Anthropic) | Official SDK for building MCP servers; stdio transport for Claude Desktop |
| Eval framework | pytest + LLM-as-judge (Claude) | Deterministic + semantic quality checks |

---

## 3. Repository Structure

```
medsafe/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, route registration
│   │   ├── config.py             # Settings (env vars, API keys)
│   │   └── dependencies.py       # Shared FastAPI deps (DB sessions, etc.)
│   ├── orchestrator/
│   │   ├── orchestrator.py       # LLM orchestrator loop
│   │   ├── classifier.py         # Query type classifier
│   │   └── planner.py            # Execution plan builder
│   ├── tools/
│   │   ├── rxnorm.py             # RxNorm REST API client
│   │   ├── openfda.py            # openFDA FAERS API client
│   │   ├── dailymed.py           # DailyMed API client
│   │   ├── interaction_checker.py # DrugBank lookup + RAG fallback
│   │   └── symptom_attributor.py  # Symptom → drug attribution
│   ├── rag/
│   │   ├── corpus/               # Raw downloaded data files
│   │   ├── ingest.py             # Chunking + embedding pipeline
│   │   ├── retriever.py          # Hybrid search (dense + BM25 + RRF)
│   │   └── reranker.py           # Cross-encoder re-ranking
│   ├── guardrails/
│   │   ├── input_guards.py       # Emergency detection, self-prescribing, PII, injection
│   │   └── output_guards.py      # Prescribing language, safety assertions, hallucination check
│   ├── models/
│   │   ├── medication.py         # Medication Pydantic model
│   │   ├── interaction.py        # Interaction Pydantic model
│   │   ├── briefing.py           # SafetyBriefing Pydantic model
│   │   └── analysis.py           # AnalysisResult model
│   ├── api/
│   │   ├── medications.py        # /api/medications/* routes
│   │   ├── analysis.py           # /api/analysis/* routes
│   │   ├── drugs.py              # /api/drugs/* routes
│   │   └── briefing.py           # /api/briefing/* routes
│   ├── eval/
│   │   ├── test_sets/            # Gold-standard test cases (JSON)
│   │   ├── runners/              # Eval runners
│   │   └── judges/               # LLM-as-judge prompts
│   └── scripts/
│       ├── ingest_dailymed.py    # Download + process DailyMed XML
│       ├── ingest_drugbank.py    # Process DrugBank open XML
│       └── ingest_nih_ods.py     # Scrape NIH ODS supplement sheets
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MedicationInput/   # Drug entry + normalization confirm
│   │   │   ├── InteractionTable/  # Ranked interaction matrix
│   │   │   ├── SymptomChecker/    # Symptom input + attribution
│   │   │   ├── SafetyBriefing/    # Full briefing view
│   │   │   ├── DrugDetail/        # Individual drug deep-dive
│   │   │   └── shared/            # UI primitives
│   │   ├── hooks/                 # Custom React hooks
│   │   ├── api/                   # API client (axios/fetch wrappers)
│   │   ├── types/                 # TypeScript types (mirrors Pydantic models)
│   │   ├── store/                 # State management (Zustand)
│   │   └── App.tsx
│   ├── index.html
│   └── vite.config.ts
├── mcp_server/
│   ├── server.py                  # MCP server entry point (stdio transport for Claude Desktop)
│   ├── tools.py                   # MCP tool definitions wrapping backend tools
│   ├── resources.py               # MCP resources (drug profiles, interaction pairs as URIs)
│   └── prompts.py                 # MCP prompt templates
├── data/                          # Downloaded raw data (gitignored)
├── tests/
├── docker-compose.yml
├── .env.example
└── plan.md
```

---

## 4. Core Data Models

### Medication
```python
class Medication(BaseModel):
    rxcui: str | None          # RxNorm Concept Unique Identifier
    name: str                  # Preferred generic name
    brand_names: list[str]
    input_text: str            # Original user input
    dose: str | None
    frequency: str | None
    type: Literal["prescription", "otc", "supplement"]
    confidence: float          # 0.0–1.0 normalization confidence
    active_compounds: list[str]  # for supplements
```

### Interaction
```python
class Interaction(BaseModel):
    drug_a: Medication
    drug_b: Medication
    severity: Literal["major", "moderate", "minor", "unknown"]
    mechanism: str              # Clinical description
    mechanism_plain: str        # Plain English
    clinical_effect: str
    evidence_level: Literal["well-documented", "theoretical", "case-reports"]
    source: InteractionSource   # DrugBank ID | FDA label section | FAERS
    confidence: Literal["high", "moderate", "low"]
```

### SafetyBriefing
```python
class SafetyBriefing(BaseModel):
    session_id: str
    generated_at: datetime
    medications: list[Medication]
    interactions: list[Interaction]        # sorted: major → moderate → minor
    symptom_attributions: list[Attribution] | None
    adverse_events: list[FAERSResult] | None
    provider_questions: list[str]          # auto-generated questions to ask
    disclaimer: str
    sources: list[Citation]
```

---

## 5. API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/medications/normalize` | Free-text → structured Medication objects |
| POST | `/api/medications/confirm` | User confirms/edits normalized list |
| POST | `/api/analysis/full` | Full pairwise interaction analysis |
| POST | `/api/analysis/add-drug` | Check new drug against existing list only |
| POST | `/api/analysis/symptoms` | Attribute symptoms to drugs in session |
| GET | `/api/drugs/{rxcui}` | Drug detail page (label sections, FAERS) |
| POST | `/api/briefing/generate` | Produce structured safety briefing |
| GET | `/api/health` | Health check |

All routes return structured JSON. Errors use RFC 7807 Problem Details format.

---

## 6. LLM Orchestrator Design

The orchestrator is NOT a simple chatbot. It is a multi-step pipeline planner.

### Query Types
1. `FULL_ANALYSIS` — "Check all my medications"
2. `INCREMENTAL_ADD` — "Can I add turmeric?"
3. `SYMPTOM_CHECK` — "I've been dizzy"
4. `DRUG_DEEP_DIVE` — "Tell me about my omeprazole"
5. `GENERAL_QUESTION` — "Is it safe long-term?"

### Tool Definitions (registered with Claude)
```python
tools = [
    normalize_medication,        # RxNorm API → structured Medication
    check_interaction_pair,      # DrugBank + RAG → Interaction record
    get_adverse_events,          # openFDA FAERS → event counts
    get_drug_label_section,      # DailyMed → label section text
    attribute_symptom,           # RAG over adverse reaction sections
    calculate_interaction_matrix # calls check_interaction_pair for all pairs
]
```

### Agentic Replanning Triggers
- **Thin data:** No DrugBank match → widen to drug class level
- **Ambiguous normalization:** Confidence < 0.9 → ask user for clarification
- **Supplement gap:** Not in RxNorm → look up active compound + CYP effects
- **New pathway found:** Symptom attribution reveals indirect interaction → re-query the implicated pair
- **Low FAERS volume:** < 10 reports → check FDA label post-marketing section instead

---

## 7. RAG Pipeline

### Corpora

| Collection | Source | Chunks | Count |
|---|---|---|---|
| FDA Drug Labels | DailyMed bulk XML | Per section (Contraindications, Warnings, Drug Interactions, Adverse Reactions) | ~140K labels → ~560K section chunks |
| Drug Interactions | DrugBank open subset | Per interaction pair | ~2,500 pairs |
| Supplement Fact Sheets | NIH ODS | Per section | ~100 supplements → ~400 chunks |
| Consumer Drug Info | MedlinePlus XML | Per page | ~1,500 pages |

**MVP scope:** Start with top 200 most-prescribed drugs + all DrugBank interactions. Expand incrementally.

### Indexing Strategy
- Embedding: `text-embedding-3-small`
- Hybrid retrieval: dense cosine similarity + BM25 keyword → combined via Reciprocal Rank Fusion (RRF)
- Metadata filtering: Always filter by `rxcui` before ranking — never retrieve atorvastatin chunks for a metformin query
- Re-ranking: `cross-encoder/ms-marco-MiniLM-L-6-v2` on top-20 retrieved chunks → pass top-5 to LLM

---

## 8. Guardrails

### Input Guardrails (pre-orchestrator)
| Check | Method | Action |
|---|---|---|
| Emergency detection | Keyword match + LLM classifier | Return Poison Control (1-800-222-1222) and 911. Stop. |
| Self-prescribing | Classifier | Redirect to healthcare provider. Stop. |
| PII detection | Regex (SSN, DOB, insurance ID) + LLM | Strip PII, warn user. |
| Prompt injection | Pattern match in drug name fields | Reject, ask re-entry. |

### Output Guardrails (post-generation)
| Check | Method | Action |
|---|---|---|
| Prescribing language | LLM classifier | Rewrite to "discuss with your provider whether..." |
| Safety assertions ("it's safe") | Classifier | Rewrite to "no known interaction found; absence of data ≠ safety" |
| Uncited claims | Source map verification | Add source from intermediate data or remove claim |
| Hallucinated interactions | Diff output claims vs. raw tool outputs | Remove hallucinated claims, log for eval |
| Missing disclaimer | String check | Append standard disclaimer |

### High-Risk Drug Categories (extra-cautious language)
- Anticoagulants (warfarin, DOACs, aspirin, clopidogrel)
- Chemotherapy / immunosuppressants
- Psychiatric (SSRIs, MAOIs, antipsychotics, benzodiazepines)
- Opioids and controlled substances
- Narrow therapeutic index (digoxin, lithium, phenytoin, theophylline)

---

## 9. Frontend Design

### Pages / Views
1. **Home / Medication Entry** — Text area for free-text drug list. Submit → normalization results.
2. **Confirm Medications** — Review normalized list, correct mismatches, add/remove items, confirm.
3. **Analysis Dashboard** — Tabbed view:
   - *Interactions* — Sortable table of all pairs, color-coded severity
   - *FAERS Data* — Adverse event counts with context
   - *Safety Briefing* — Full structured report
4. **Symptom Checker** — Add symptoms, see ranked attribution with evidence
5. **Drug Detail** — Per-drug deep-dive: label sections, FAERS summary, plain-language profile
6. **Add Drug** — Incremental check: enter new drug, see only new interactions

### State Management (Zustand)
```
sessionStore:
  - medications: Medication[]        # confirmed list
  - analysisResult: AnalysisResult | null
  - briefing: SafetyBriefing | null
  - isLoading: boolean
  - currentStep: "input" | "confirm" | "analysis" | "briefing"
```

### Key UX Principles
- Always show source citations inline (collapsible)
- Color code severity: red = major, orange = moderate, yellow = minor
- Disclaimer banner persistent at top during analysis views
- Never show a blank "no interactions" — always include uncertainty disclosure
- Symptom attribution clearly framed as hypotheses ("possible association"), not diagnoses

---

## 10. MCP Server Design

### Architecture Note
When MedSafe runs as an MCP plugin, **Claude itself is the orchestrator** — it decides which tools to call and in what order, using its own reasoning. The `backend/orchestrator/` is only used by the FastAPI path (React app). The MCP server is a thin adapter that exposes the same underlying tools directly to Claude.

This means the shared business logic (`backend/tools/`, `backend/rag/`, `backend/guardrails/`, `backend/models/`) is imported and used by both the FastAPI routes and the MCP server.

```
                    ┌─────────────────┐
                    │  Shared Core     │
                    │  tools/          │
                    │  rag/            │
                    │  guardrails/     │
                    │  models/         │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
   ┌──────────▼──────────┐     ┌────────────▼────────────┐
   │  FastAPI (REST API)  │     │     MCP Server           │
   │  + Orchestrator      │     │  (stdio transport)       │
   │  ↑ used by React app │     │  ↑ used by Claude        │
   └─────────────────────┘     └─────────────────────────┘
```

### MCP Tools (exposed to Claude)

| Tool name | Description | Inputs | Output |
|---|---|---|---|
| `normalize_medications` | Resolve free-text drug names to structured objects | `medications: list[str]` | `list[Medication]` |
| `check_interactions` | Pairwise interaction matrix for a confirmed drug list | `medications: list[Medication]` | `list[Interaction]` |
| `get_adverse_events` | FAERS adverse event data for a drug combination | `drug_names: list[str]` | `FAERSResult` |
| `get_drug_label` | Retrieve a specific FDA label section | `rxcui: str, section: str` | Label text + citation |
| `attribute_symptoms` | Attribute reported symptoms to drugs in the list | `symptoms: list[str], medications: list[Medication]` | `list[Attribution]` |
| `add_drug_check` | Check a new drug against an existing confirmed list | `existing: list[Medication], new_drug: str` | `list[Interaction]` (new pairs only) |
| `full_analysis` | End-to-end: normalize → interactions → briefing | `medications: list[str]` | `SafetyBriefing` |

`full_analysis` is the high-value composite tool — a single call Claude can make to get a complete briefing. The granular tools exist for conversational follow-up ("what about this specific pair?").

### MCP Resources (URI-addressable data)

| URI pattern | Description |
|---|---|
| `medsafe://drug/{rxcui}` | Drug profile: name, type, label summary, known interaction count |
| `medsafe://interaction/{rxcui_a}/{rxcui_b}` | Specific pair interaction record |

Resources let Claude attach drug profiles to its context without a tool call.

### MCP Prompts (templates)

| Prompt name | Purpose |
|---|---|
| `medication_safety_analysis` | Pre-fills a full analysis request; user just fills in their drug list |
| `symptom_check` | Pre-fills a symptom attribution request with the current session's drug list |

### Transport & Installation

The MCP server runs over **stdio** (subprocess), which is what Claude Desktop and claude.ai use.

**Claude Desktop config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "medsafe": {
      "command": "python",
      "args": ["/path/to/medsafe/mcp_server/server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-...",
        "OPENFDA_API_KEY": "...",
        "CHROMA_PERSIST_PATH": "/path/to/medsafe/data/chroma",
        "DRUGBANK_SQLITE_PATH": "/path/to/medsafe/data/drugbank.db"
      }
    }
  }
}
```

### Guardrails in MCP Context
Output guardrails still run inside each tool implementation — they are not skipped just because the caller is Claude. Input guardrails (emergency detection, PII) also run inside `normalize_medications` and `full_analysis`. Claude sees the guardrail-filtered output, not the raw LLM generation.

---

## 11. Week-by-Week Build Plan

### Week 1 — Foundation + Normalization
**Backend:**
- [ ] Initialize FastAPI project, Docker Compose, `.env.example`
- [ ] Implement `Medication`, `Interaction`, `SafetyBriefing` Pydantic models
- [ ] Build RxNorm API client (`tools/rxnorm.py`)
  - `/approximateTerm` for fuzzy matching
  - `/rxcui/{id}/allrelated` for metadata
  - Supplement fallback table (top 50 common supplements → active compounds)
- [ ] Implement normalization pipeline (tokenize → preprocess → RxNorm → dosage extract → confidence score)
- [ ] Wire `/api/medications/normalize` and `/api/medications/confirm` routes
- [ ] Input guardrails: emergency detection, PII stripping

**Frontend:**
- [ ] Initialize React + Vite + TypeScript + Tailwind + shadcn/ui
- [ ] Medication entry page with multi-line input
- [ ] Normalization confirmation view (show resolved names, allow corrections)
- [ ] API client module

**Eval:**
- [ ] Build normalization test set: 200 inputs (brand names, generics, colloquialisms, supplements) with gold RxCUIs
- [ ] Run eval, target > 95% accuracy

**Deliverable:** User enters "Lipitor, baby aspirin, turmeric" and sees normalized results with confidence scores.

---

### Week 2 — RAG Pipeline
**Backend:**
- [ ] Script: Download top 200 DailyMed labels as bulk XML (`scripts/ingest_dailymed.py`)
  - Parse SPL XML → extract sections by LOINC code
  - Chunk by section (Contraindications, Warnings, Drug Interactions, Adverse Reactions)
  - Attach metadata: `rxcui`, `section_type`, `label_version_date`
- [ ] Script: Process DrugBank open XML (`scripts/ingest_drugbank.py`)
  - Parse interaction entries → normalize drug names to RxCUI
  - Store structured records in SQLite + embed descriptions
- [ ] Script: Process NIH ODS supplement fact sheets (`scripts/ingest_nih_ods.py`)
- [ ] Implement ChromaDB setup with metadata filtering (`rag/ingest.py`)
- [ ] Implement hybrid retriever: dense + BM25 + RRF (`rag/retriever.py`)
- [ ] Implement cross-encoder re-ranker (`rag/reranker.py`)

**Deliverable:** Given `rxcui_a` and `rxcui_b`, retrieve relevant interaction data from corpus with source metadata.

---

### Week 3 — Interaction Engine
**Backend:**
- [ ] Implement `check_interaction_pair` tool:
  - First: direct DrugBank SQLite lookup by RxCUI pair
  - Fallback: RAG retrieval over FDA label Drug Interactions sections
  - Returns: severity, mechanism, plain-language description, evidence level, source
- [ ] Implement `calculate_interaction_matrix`: calls `check_interaction_pair` for all N×(N-1)/2 pairs, async batch
- [ ] Implement severity classifier (DrugBank severity + LLM classification for RAG-sourced results)
- [ ] Wire `/api/analysis/full` route
- [ ] Basic output guardrails: source citation check, prescribing language check

**Frontend:**
- [ ] Interaction table component: sortable by severity, expandable rows showing mechanism + source
- [ ] Severity color coding + badge system
- [ ] Persistent disclaimer banner

**Eval:**
- [ ] Build interaction test set: 100 known interaction pairs + 50 known non-interacting pairs
- [ ] Run recall and precision eval, target > 90% recall, > 90% precision

**Deliverable:** User confirms medication list, sees ranked interaction table with severity and cited sources.

---

### Week 4 — Orchestrator + Safety Briefing
**Backend:**
- [ ] Implement query classifier (`orchestrator/classifier.py`) — classifies input into 5 query types
- [ ] Implement orchestrator loop (`orchestrator/orchestrator.py`):
  - Claude API integration with tool-calling
  - Execution plan builder per query type
  - Agentic replanning: thin data widening, ambiguity re-query, drug class fallback
- [ ] Implement safety briefing generator: synthesizes interaction matrix + FAERS + attributions into structured output
- [ ] Wire `/api/briefing/generate`
- [ ] LangSmith tracing integration
- [ ] Output guardrails: full suite (hallucination check, uncited claims, safety assertions)

**Frontend:**
- [ ] Safety briefing view: medication summary table, interaction flags, auto-generated provider questions, sources
- [ ] Add drug flow (`/api/analysis/add-drug`) with delta briefing display
- [ ] Loading states and skeleton UIs for async pipeline

**MCP Server:**
- [ ] Initialize `mcp_server/` with `mcp` Python SDK
- [ ] Implement `server.py` entry point with stdio transport
- [ ] Implement `tools.py` — wrap all 7 backend tools as MCP tools
- [ ] Implement `resources.py` — `medsafe://drug/{rxcui}` and `medsafe://interaction/{rxcui_a}/{rxcui_b}`
- [ ] Implement `prompts.py` — `medication_safety_analysis` and `symptom_check` templates
- [ ] Wire Claude Desktop config and test end-to-end in Claude Desktop

**Deliverable:** Full end-to-end `FULL_ANALYSIS` flow working in both the React app and Claude Desktop via MCP.

---

### Week 5 — FAERS + Symptoms + Agentic Loops
**Backend:**
- [ ] Implement openFDA FAERS client (`tools/openfda.py`):
  - Query by drug name combinations
  - Parse: event counts, serious outcomes (hospitalization, death, disability), top reported reactions
  - Contextualize with denominator and reporter type
  - Flag when data is sparse (< 10 reports)
- [ ] Implement symptom attributor (`tools/symptom_attributor.py`):
  - RAG over FDA label Adverse Reactions sections
  - Cross-reference against interaction effects in current list
  - Rank by likelihood + evidence strength
  - Frame as hypotheses, not diagnoses
- [ ] Wire `/api/analysis/symptoms`
- [ ] Complete all agentic loop replanning patterns
- [ ] Implement `INCREMENTAL_ADD`, `SYMPTOM_CHECK`, `DRUG_DEEP_DIVE`, `GENERAL_QUESTION` query types

**Frontend:**
- [ ] FAERS data panel: adverse event counts with contextual framing
- [ ] Symptom checker: free-text input, ranked attribution list with evidence
- [ ] Drug detail page: label sections, FAERS summary, plain-language profile
- [ ] All 5 query type flows connected to UI

**Deliverable:** All five query types working. FAERS data shown with context. Symptom attribution live.

---

### Week 6 — Evals + Hardening + Polish
**Backend:**
- [ ] Complete deterministic eval suite:
  - Normalization accuracy (200 inputs, target > 95%)
  - Interaction recall (100 pairs, target > 90%)
  - Interaction precision (50 non-interacting pairs, target > 90%)
  - Severity classification (target > 85% agreement)
  - Source traceability (target 100% citation rate)
  - Guardrail compliance (50 adversarial inputs, target 100% catch rate)
- [ ] LLM-as-judge eval suite:
  - Faithfulness: every claim grounded in retrieved sources (target > 95%)
  - Readability: Flesch-Kincaid ≤ 8 (target avg ≥ 4.0/5)
  - Completeness (target avg ≥ 4.0/5)
  - Tone appropriateness (target 2.5–3.5/5)
- [ ] Run all 8 benchmark test scenarios (S-01 through S-08)
- [ ] Performance optimization: parallel async API calls, RxNorm response caching
- [ ] Adversarial guardrail testing

**Frontend:**
- [ ] Polish all views
- [ ] Error states and empty states
- [ ] Responsive layout
- [ ] Accessibility pass (ARIA labels, keyboard nav)

**Deliverable:** Production-ready demo with documented eval results.

---

## 12. Benchmark Test Scenarios

| ID | Medication List | Expected Behavior |
|---|---|---|
| S-01 | Warfarin + Aspirin | Major interaction (bleeding risk). High confidence. FDA label + DrugBank citation. |
| S-02 | Atorvastatin + Turmeric | Moderate interaction (CYP3A4 inhibition). Lower evidence level noted. |
| S-03 | Metformin + Lisinopril + Atorvastatin + Omeprazole + Aspirin + Fish Oil + Turmeric | 21 pairs checked. Flag: aspirin+fish oil, aspirin+turmeric, atorvastatin+turmeric, omeprazole+metformin. |
| S-04 | S-03 list + "muscle aches and dizziness" | Muscle aches → atorvastatin (primary), atorvastatin+curcumin interaction (secondary). Dizziness → lisinopril. |
| S-05 | Phenelzine (MAOI) + Fluoxetine (SSRI) | MAJOR / life-threatening. Serotonin syndrome risk. Strongest possible language. Immediate provider consult. |
| S-06 | Acetaminophen + Cetirizine | "No known interactions found" with uncertainty disclosure. |
| S-07 | Lisinopril + "ashwagandha root extract" | Normalize ashwagandha. Flag limited evidence. Note potential thyroid/BP effects. Explicit uncertainty. |
| S-08 | "my heart pill, the white round one" | Graceful failure. Ask for clarification. Do not guess. |

---

## 13. External Data Sources

| Source | Access | Notes |
|---|---|---|
| RxNorm | REST API, no auth | Live queries. Cache locally for top 500 drugs. |
| openFDA FAERS | REST API, optional key | Live queries per session. Not pre-indexed. |
| DailyMed | Bulk XML download | One-time download + re-index. Start with top 200 drugs. |
| DrugBank (open subset) | XML download | CC BY-NC 4.0. ~2,500 interaction pairs. |
| NIH ODS | HTML/PDF scrape | ~100 supplement fact sheets. |
| MedlinePlus | XML feed | ~1,500 drug pages for plain-language context. |

---

## 14. Environment Variables

```env
ANTHROPIC_API_KEY=
OPENAI_API_KEY=               # for text-embedding-3-small
OPENFDA_API_KEY=              # optional, increases rate limit
LANGSMITH_API_KEY=            # for tracing
CHROMA_PERSIST_PATH=./data/chroma
DRUGBANK_SQLITE_PATH=./data/drugbank.db
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173
```

---

## 15. Key Technical Decisions

**React over Streamlit:** PRD listed Streamlit as MVP and React as stretch. Since we're building from the start with React, we get a production-quality UI without refactoring later. Adds ~1 week of frontend work but avoids technical debt.

**Claude claude-sonnet-4-6 as orchestrator:** The PRD specifies Claude 3.5 Sonnet; we'll use the newer claude-sonnet-4-6 (our current environment default), which has the same strong tool-calling characteristics with improved performance.

**SQLite for DrugBank + Chroma for RAG:** Structured DrugBank interaction pairs (drug_a, drug_b, severity) are best stored in SQL for O(1) exact lookups. RAG is reserved for unstructured label text where fuzzy retrieval adds value.

**Hybrid retrieval (dense + BM25):** Drug names and RxCUI codes are exact tokens that BM25 handles better than dense search. Combining both via RRF outperforms either alone for medical text.

**Session-only storage:** No PII stored beyond the active session. Medication lists live in browser state (Zustand). Backend is stateless per request.

**MCP server skips the orchestrator:** When Claude Desktop calls MedSafe tools, Claude is the orchestrator — it decides which tools to call. The `backend/orchestrator/` is only needed for the FastAPI path where we need a deterministic pipeline without relying on the calling LLM. This avoids duplicating orchestration logic and keeps the MCP server lean.

**Guardrails apply at the tool layer, not the interface layer:** Both the FastAPI routes and MCP tools funnel through the same `guardrails/` implementations. This ensures safety constraints are enforced regardless of which interface is used.

---

## 16. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| RxNorm API rate limiting | Normalization fails | Cache responses locally; offline fallback for top 500 drugs |
| DrugBank open subset missing interactions | False negatives | DrugBank primary + FDA labels fallback; document coverage gaps in eval |
| LLM hallucinating interactions | False safety information | Output guardrail: every claim must trace to a raw tool output |
| openFDA FAERS data is noisy | Misleading event counts | Always show denominator + reporter type; flag FAERS limitations in UI |
| Supplement data is sparse | System can't assess many supplements | Always state when data is unavailable; never infer safety from absence |
| React frontend scope creep | Timeline risk | Scope: 6 views only (listed above). No auth, no PDF export in MVP. |
| DailyMed bulk download time | Blocks week 2 | Start download in week 1 evenings. Use top-200 subset to start. |

---

## 17. Out of Scope (MVP)

- PDF export of safety briefing (stretch goal post-week 6)
- User accounts / persistent history
- Multi-language support
- Provider-facing vs. patient-facing format toggle
- Supplement-specific NIH ODS RAG corpus (ODS scraped but not indexed until week 5+)
- Mobile app
