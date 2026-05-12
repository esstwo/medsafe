# Week 5 — FAERS + Symptoms + Agentic Loops

## What We're Building and Why

Fills in the two Week 4 stubs: real FAERS adverse event data from openFDA, and Claude+RAG-based symptom attribution. Both wire into existing SafetyBriefing model fields (adverse_events, symptom_attributions) that are currently null. Also indexes NIH ODS supplement fact sheets into ChromaDB.

**Deliverable:** Briefing shows real FAERS counts per drug + top reactions; symptom input returns ranked attribution with evidence from FDA labels. MCP tools fully functional.

## Implementation Tasks

- [x] backend/tools/openfda.py — async FAERS client
- [x] backend/tools/symptom_attributor.py — RAG + Claude attribution
- [x] backend/orchestrator/briefing_generator.py — add FAERS + symptom enrichment
- [x] backend/api/analysis.py — POST /api/analysis/symptoms
- [x] mcp_server/mcp_tools.py — replace 2 stubs
- [x] backend/rag/ingest.py — add ingest_nih_ods()
- [x] frontend/src/types/index.ts — fix null types, add FAERSResult + Attribution
- [x] frontend/src/api/analysis.ts — add attributeSymptoms()
- [x] frontend/src/store/sessionStore.ts — add symptoms field
- [x] frontend/src/components/SafetyBriefing/index.tsx — FAERS panel + symptom checker

## Changes Made

### Backend Tools
- openfda.py: 3 parallel FAERS calls (total, serious, top reactions) with brand-name fallback; data_sparse flag for <10 reports; get_faers_batch() deduplicates by name
- symptom_attributor.py: RAG over Adverse Reactions sections → Claude Haiku extraction; builds Attribution with citation from setid

### Orchestrator
- briefing_generator.py: generate_briefing() accepts optional symptoms + include_faers params; parallel fetch FAERS + attribution

### API
- analysis.py: POST /api/analysis/symptoms with AttributionResponse

### MCP
- mcp_tools.py: get_adverse_events → get_faers_data(); attribute_symptoms → attribute_symptoms()

### Frontend
- Types: FAERSResult, Attribution interfaces; SafetyBriefing properly typed
- Store: symptoms: string[] field added
- API: attributeSymptoms() client
- SafetyBriefing: FAERS panel + symptom checker textarea + attribution results
