# MedSafe — Claude Working Instructions

## Project Overview

MedSafe is an AI-powered drug interaction and safety advisor. It ships as two interfaces over one shared core:
- **FastAPI + React** — standalone web app
- **MCP server** — Claude plugin usable inside Claude Desktop / claude.ai

Full architecture and 6-week build plan is in `plan.md`.

---

## Workflow: Before Starting Any Task

1. **Always enter plan mode first.** Think through the approach before writing any code.

2. **Write the plan to `.claude/tasks/TASK_NAME.md`** before doing anything else. The plan must include:
   - What we're building and why (reasoning, not just what)
   - Step-by-step implementation tasks broken down small enough to execute one at a time
   - Any external dependencies or packages needed (with version research — see below)
   - Edge cases and guardrail considerations specific to this task
   - How this fits into the broader architecture in `plan.md`

3. **Research before assuming.** If the task touches an external API, library, or package you haven't used recently, use the Task tool to look up current docs, latest stable versions, and any breaking changes. Do not guess at API shapes.

4. **Think MVP.** Do not over-plan or over-engineer. The plan should only cover what's needed for the current task. Stretch goals go to the bottom under a clearly labeled "Out of scope" section.

5. **Ask for review before implementing.** After writing the plan to `.claude/tasks/TASK_NAME.md`, stop and ask the user to review it. Do not write any implementation code until the plan is explicitly approved.

---

## Workflow: While Implementing

6. **Update the plan as you work.** If you discover something that changes the approach mid-task, update `.claude/tasks/TASK_NAME.md` to reflect the actual approach taken — not just the original plan.

7. **Mark tasks complete as you finish them.** Use checkboxes in the plan file. Check off each sub-task as soon as it's done, not in batches at the end.

8. **Append a change log to the plan file after completing each major sub-task.** Format:

   ```
   ## Changes Made

   ### <Sub-task name>
   - What files were created or modified (with paths)
   - What the implementation does and any non-obvious decisions
   - Any deviations from the original plan and why
   ```

   This allows another engineer to pick up where you left off without needing to read the full diff.

---

## Project-Specific Rules

### Safety Guardrails (non-negotiable)
- Never generate output that recommends starting, stopping, or changing any medication
- Never assert that a drug combination is "safe" — only that "no known interaction was found"
- Never provide a diagnosis — symptom attributions are always framed as hypotheses
- Every factual claim must cite a source: DrugBank ID, FDA label section, or FAERS query
- Uncertainty must be stated explicitly when evidence is thin, sparse, or conflicting
- Emergency inputs ("I took too many pills") must redirect to Poison Control (1-800-222-1222) and 911

### High-Risk Drug Categories
Extra-cautious language required for: anticoagulants, chemotherapy/immunosuppressants, psychiatric meds (SSRIs/MAOIs/antipsychotics/benzodiazepines), opioids, narrow therapeutic index drugs (digoxin, lithium, phenytoin, theophylline).

### Code Style
- Python: type hints everywhere, Pydantic models for all data shapes, async/await for external API calls
- React: TypeScript strict mode, functional components only, no `any`
- No comments that explain what the code does — only comments explaining non-obvious WHY (hidden constraint, workaround, subtle invariant)
- No error handling for impossible scenarios — only validate at system boundaries (user input, external APIs)

### Architecture Boundaries
- Backend is stateless per request — no session state stored server-side
- No PII stored beyond the active browser session
- DrugBank structured records → SQLite (exact lookup). Unstructured label text → ChromaDB (RAG retrieval). Do not mix these.
- All RAG retrievals must be filtered by `rxcui` metadata before ranking
- **Shared core rule:** `backend/tools/`, `backend/rag/`, `backend/guardrails/`, and `backend/models/` are imported by both FastAPI and the MCP server. Never put interface-specific logic in the shared core.
- **MCP vs FastAPI orchestration:** The MCP server has no orchestrator — Claude is the orchestrator. The `backend/orchestrator/` is only used by the FastAPI path. Do not call the orchestrator from MCP tool handlers.
- **Guardrails always run at the tool layer** — never skip them based on which interface is calling.

---

## Repository Layout (quick reference)

```
medsafe/
├── backend/                  # ← shared core + FastAPI interface
│   ├── app/                  # FastAPI entry point and routes
│   ├── orchestrator/         # LLM orchestrator (FastAPI path only — NOT used by MCP)
│   ├── tools/                # ← SHARED: RxNorm, openFDA, DailyMed, interaction checker, symptom attributor
│   ├── rag/                  # ← SHARED: corpus ingestion, hybrid retrieval, re-ranking
│   ├── guardrails/           # ← SHARED: input + output guardrail implementations
│   ├── models/               # ← SHARED: Pydantic data models
│   ├── api/                  # Route handlers (FastAPI path only)
│   ├── eval/                 # Eval framework and test sets
│   └── scripts/              # Data ingestion scripts
├── mcp_server/               # ← MCP interface (thin adapter over shared core)
│   ├── server.py             # Entry point — stdio transport for Claude Desktop
│   ├── tools.py              # MCP tool definitions wrapping backend/tools/
│   ├── resources.py          # medsafe://drug/{rxcui}, medsafe://interaction/{a}/{b}
│   └── prompts.py            # Prompt templates for Claude
├── frontend/
│   └── src/
│       ├── components/       # MedicationInput, InteractionTable, SymptomChecker, SafetyBriefing, DrugDetail
│       ├── api/              # API client wrappers
│       ├── store/            # Zustand state (medications, analysisResult, briefing, currentStep)
│       └── types/            # TypeScript types mirroring Pydantic models
├── data/                     # Downloaded raw data (gitignored)
├── .claude/tasks/            # Per-task implementation plans
├── plan.md                   # Full 6-week implementation plan
└── CLAUDE.md                 # This file
```

---

## Build Sequence (from plan.md)

| Week | Focus | Key Deliverable |
|---|---|---|
| 1 | Foundation + normalization | Enter drugs → see normalized results |
| 2 | RAG pipeline | Drug pair → retrieve interaction data |
| 3 | Interaction engine | Medication list → ranked interaction table |
| 4 | Orchestrator + briefing + **MCP server** | Full FULL_ANALYSIS in React app AND Claude Desktop |
| 5 | FAERS + symptoms + agentic loops | All 5 query types live in both interfaces |
| 6 | Evals + hardening + polish | Production-ready demo with eval results |
