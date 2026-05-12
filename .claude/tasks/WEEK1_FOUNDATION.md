# Week 1 — Foundation + Normalization

## What We're Building and Why

Building the skeleton the entire project sits on: directory structure, shared Pydantic models, RxNorm drug normalization pipeline, input guardrails, two API endpoints, and the React UI through the "confirm medications" step.

Normalization is deterministic (RxNorm API + supplement fallback table). No LLM involved until Week 4 when the orchestrator arrives. The `backend/tools/` code built here becomes the tool functions Claude calls in Week 4.

**Deliverable:** `Lipitor, baby aspirin, turmeric` → normalized results with confidence scores.

## Implementation Tasks

- [x] Repository scaffold (directories, __init__.py files)
- [x] `.gitignore`, `.env.example`, `docker-compose.yml`, `backend/Dockerfile`
- [x] `backend/pyproject.toml` with pinned dependencies
- [x] `backend/app/config.py` — pydantic-settings Settings
- [x] `backend/app/main.py` — FastAPI app, CORS, health endpoint
- [x] `backend/models/medication.py` — Medication model
- [x] `backend/models/interaction.py` — Interaction stub
- [x] `backend/models/analysis.py` — AnalysisResult stub
- [x] `backend/models/briefing.py` — SafetyBriefing stub
- [x] `backend/tools/rxnorm.py` — async RxNorm client + supplement fallback table
- [x] `backend/tools/normalizer.py` — normalization pipeline
- [x] `backend/guardrails/input_guards.py` — emergency detection + PII strip
- [x] `backend/api/medications.py` — normalize + confirm routes
- [x] Wire routes into main.py
- [x] Frontend: Vite + React + TypeScript + Tailwind + shadcn/ui init
- [x] `frontend/src/types/index.ts` — TypeScript mirrors of Pydantic models
- [x] `frontend/src/store/sessionStore.ts` — Zustand store
- [x] `frontend/src/api/medications.ts` — API client
- [x] `frontend/src/components/MedicationInput/` — drug entry + submit
- [x] `frontend/src/components/ConfirmMedications/` — review + confirm table
- [x] `frontend/src/App.tsx` — step router

## External Dependencies

| Package | Version |
|---|---|
| fastapi | 0.115.* |
| uvicorn[standard] | 0.34.* |
| pydantic | 2.* |
| pydantic-settings | 2.* |
| httpx | 0.28.* |
| python-dotenv | 1.* |
| pytest | 8.* |
| pytest-asyncio | 0.24.* |
| zustand | 5.* |
| axios | 1.* |

## Edge Cases

- Dose baked into name ("Tylenol 500mg") → strip dose before RxNorm lookup
- Supplement not in fallback table → confidence=0.5, warning added
- Empty input → 400 before normalization
- Emergency phrasing in drug field → guardrail hard-stop with Poison Control number
- PII in free text → strip + warn, continue with remaining text
- RxNorm API timeout → return confidence=0.0 entry, flag as "lookup failed"

## Changes Made

### Repository scaffold + backend infrastructure
- Created all directories per CLAUDE.md layout
- `backend/pyproject.toml`: pinned fastapi 0.115, uvicorn, pydantic v2, httpx 0.28, pytest 8
- `backend/app/config.py`: pydantic-settings BaseSettings with CORS, API keys, log level
- `backend/app/main.py`: FastAPI with lifespan, CORS middleware, /api/health, includes medication router
- `backend/models/`: Medication (full), Interaction/AnalysisResult/SafetyBriefing (stubs for Week 3+)

### RxNorm client + normalization pipeline
- `backend/tools/rxnorm.py`: async httpx client, approximate_term(), get_drug_info(), supplement fallback table (50 entries)
- `backend/tools/normalizer.py`: preprocess → RxNorm lookup → confidence scoring → supplement fallback → type classification → brand name lookup

### Guardrails
- `backend/guardrails/input_guards.py`: emergency keyword check (hard stop), PII regex strip (SSN, DOB, insurance ID)

### API routes
- `backend/api/medications.py`: POST /normalize (guards → normalize → return), POST /confirm (validate → echo + session_id)
