# Week 4 — Orchestrator + Safety Briefing + MCP Server

## What We're Building and Why

Three additions on top of Weeks 1–3:
1. **Orchestrator** — query classifier (5 types), Claude tool-calling loop with agentic replanning, safety briefing generator (synthesises interaction data → provider questions via Claude, LangSmith-traced)
2. **API endpoints** — POST /api/briefing/generate, POST /api/analysis/add-drug
3. **MCP server** — thin stdio adapter so Claude Desktop can call all shared-core tools directly

**Deliverable:** Full FULL_ANALYSIS working in React app (analysis → briefing) AND in Claude Desktop via MCP.

## Implementation Tasks

### Backend
- [x] pyproject.toml — add mcp>=1.0,<2 and langsmith>=0.1
- [x] orchestrator/classifier.py — heuristic + Claude query-type classifier
- [x] orchestrator/briefing_generator.py — AnalysisResult → SafetyBriefing (LangSmith-traced)
- [x] orchestrator/orchestrator.py — Claude tool-calling loop + agentic replanning
- [x] api/briefing.py — POST /api/briefing/generate
- [x] api/analysis.py — add POST /api/analysis/add-drug
- [x] app/main.py — register briefing router

### MCP Server
- [x] mcp_server/server.py — entry point
- [x] mcp_server/tools.py — 7 tool definitions
- [x] mcp_server/resources.py — medsafe:// URI resources
- [x] mcp_server/prompts.py — prompt templates
- [x] Claude Desktop config updated

### Frontend
- [x] types/index.ts — SafetyBriefing, Citation, AddDrugResponse
- [x] store/sessionStore.ts — briefing field
- [x] api/briefing.ts — generateBriefing()
- [x] api/analysis.ts — addDrug()
- [x] components/SafetyBriefing/index.tsx
- [x] components/InteractionTable/index.tsx — briefing button + add-drug input
- [x] App.tsx — briefing step

## Changes Made

### Orchestrator
- classifier.py: heuristic keyword patterns first, Claude fallback for ambiguous cases
- briefing_generator.py: compile sources → Claude provider_questions → SafetyBriefing; @traceable for LangSmith
- orchestrator.py: 7 tool definitions, agentic loop, replanning (low confidence, empty RAG, supplement gap)

### API
- api/briefing.py: thin route delegating to briefing_generator
- api/analysis.py: add-drug endpoint — guard → normalize → pairwise check → output guard

### MCP Server
- server.py: sys.path to backend, Server("medsafe"), stdio_server transport
- tools.py: 7 handlers with guardrails; stubs for get_adverse_events + attribute_symptoms
- resources.py: medsafe://drug/{rxcui}, medsafe://interaction/{a}/{b}
- prompts.py: medication_safety_analysis, symptom_check templates

### Frontend
- SafetyBriefing component: medications, flagged interactions, provider questions, sources, disclaimer
- InteractionTable: "Generate Safety Briefing" button + "Add another drug" inline input
- Store + types + API client updated
