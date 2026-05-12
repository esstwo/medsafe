# Week 3 — Interaction Engine

## What We're Building and Why

Wires Weeks 1–2 together: normalization + RAG retrieval → structured `Interaction` objects with severity, mechanism, plain-language explanation, and source citations. Uses Claude (haiku) to extract structure from FDA label text and enrich Supabase stub descriptions. Surfaces results in a sortable, colour-coded interaction table in the React UI.

**Deliverable:** User confirms medication list → POST /api/analysis/full → ranked interaction table (major → minor) with expandable rows.

## Implementation Tasks

- [x] `backend/pyproject.toml` — add anthropic==0.55.*
- [x] `backend/tools/interaction_checker.py` — check_interaction_pair + calculate_interaction_matrix
- [x] `backend/guardrails/output_guards.py` — prescribing language + citation checks
- [x] `backend/api/analysis.py` — POST /api/analysis/full
- [x] `backend/app/main.py` — register analysis router
- [x] `backend/eval/test_sets/interaction_pairs.json` — 25-pair ground-truth set
- [x] `backend/eval/runners/eval_interactions.py` — recall/precision eval script
- [x] `frontend/src/types/index.ts` — Interaction, AnalysisResult types
- [x] `frontend/src/store/sessionStore.ts` — add analysisResult field
- [x] `frontend/src/api/analysis.ts` — runFullAnalysis() API client
- [x] `frontend/src/components/InteractionTable/index.tsx` — table UI
- [x] `frontend/src/App.tsx` — render InteractionTable on analysis step

## Changes Made

### Backend
- `backend/tools/interaction_checker.py`: Supabase lookup → RAG retrieval → Claude extraction pipeline. Semaphore(3) for concurrent pair checks. High-risk drug amplification in mechanism_plain.
- `backend/guardrails/output_guards.py`: prescribing language detection + redirect append, citation presence check.
- `backend/api/analysis.py`: POST /api/analysis/full — validates ≥2 meds, calls calculate_interaction_matrix, applies output guards.
- `backend/app/main.py`: registered analysis_router at /api/analysis.

### Eval
- `backend/eval/test_sets/interaction_pairs.json`: 25 known pairs + 5 non-interacting pairs from stub seed.
- `backend/eval/runners/eval_interactions.py`: runs check_interaction_pair against test set, reports recall/specificity.

### Frontend
- Types: InteractionSource, Interaction, AnalysisResult added to types/index.ts
- Store: analysisResult + setAnalysisResult added to sessionStore
- API: analysis.ts with runFullAnalysis()
- InteractionTable: sortable by severity, expandable rows, colour-coded badges, "no interactions" empty state
- ConfirmMedications: calls runFullAnalysis on confirm, transitions to analysis step
- App.tsx: renders InteractionTable on analysis step
