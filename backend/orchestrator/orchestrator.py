"""
FastAPI-path orchestrator — Claude tool-calling loop with agentic replanning.

NOT used by the MCP server. Claude Desktop is its own orchestrator.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.config import get_settings
from models.analysis import AnalysisResult
from models.briefing import SafetyBriefing
from models.medication import Medication
from orchestrator.classifier import QueryType

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 8

# ---------------------------------------------------------------------------
# Tool definitions (registered with Claude)
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "normalize_medications",
        "description": "Resolve free-text drug names to structured Medication objects via RxNorm.",
        "input_schema": {
            "type": "object",
            "properties": {"raw_input": {"type": "string", "description": "Comma or newline separated drug names"}},
            "required": ["raw_input"],
        },
    },
    {
        "name": "calculate_interaction_matrix",
        "description": "Compute all pairwise drug interactions for a confirmed medication list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "medications": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of Medication objects (output of normalize_medications)",
                }
            },
            "required": ["medications"],
        },
    },
    {
        "name": "generate_briefing",
        "description": "Synthesise an AnalysisResult into a full SafetyBriefing with provider questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_result": {"type": "object", "description": "AnalysisResult from calculate_interaction_matrix"}
            },
            "required": ["analysis_result"],
        },
    },
    {
        "name": "get_drug_label",
        "description": "Retrieve an FDA label section for a specific drug.",
        "input_schema": {
            "type": "object",
            "properties": {
                "rxcui": {"type": "string"},
                "section": {
                    "type": "string",
                    "enum": ["Drug Interactions", "Warnings", "Contraindications", "Adverse Reactions"],
                    "default": "Drug Interactions",
                },
            },
            "required": ["rxcui"],
        },
    },
    {
        "name": "add_drug_check",
        "description": "Check a new drug against an existing confirmed list. Returns only the new interaction pairs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "existing_medications": {"type": "array", "items": {"type": "object"}},
                "new_drug": {"type": "string"},
            },
            "required": ["existing_medications", "new_drug"],
        },
    },
    {
        "name": "check_interaction_pair",
        "description": "Check for a known interaction between exactly two drugs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "med_a": {"type": "object"},
                "med_b": {"type": "object"},
            },
            "required": ["med_a", "med_b"],
        },
    },
    {
        "name": "get_adverse_events",
        "description": "Get FAERS adverse event counts for a drug (stub — Week 5 implementation).",
        "input_schema": {
            "type": "object",
            "properties": {"drug_name": {"type": "string"}},
            "required": ["drug_name"],
        },
    },
]

# ---------------------------------------------------------------------------
# System prompts per query type
# ---------------------------------------------------------------------------

_BASE_SYSTEM = (
    "You are MedSafe, an AI-powered drug interaction and safety advisor. "
    "You have access to tools for normalizing drug names, checking interactions, "
    "retrieving FDA label data, and generating safety briefings. "
    "NEVER recommend starting, stopping, or changing any medication. "
    "Every factual claim must be grounded in tool output. "
    "Always frame findings as information, not medical advice. "
    "State uncertainty explicitly when data is limited."
)

_SYSTEM_BY_TYPE: dict[QueryType, str] = {
    QueryType.FULL_ANALYSIS: (
        _BASE_SYSTEM + "\n\nFor this full analysis: "
        "1. Normalize all drug names. "
        "2. Calculate the full interaction matrix. "
        "3. Generate a safety briefing with provider questions."
    ),
    QueryType.INCREMENTAL_ADD: (
        _BASE_SYSTEM + "\n\nThe user wants to add one new drug to their existing list. "
        "Use add_drug_check to check only the new pairs (do not recheck existing pairs)."
    ),
    QueryType.SYMPTOM_CHECK: (
        _BASE_SYSTEM + "\n\nThe user is reporting a symptom. "
        "Use get_drug_label to look up Adverse Reactions sections for their current medications. "
        "Frame findings as possible associations — never diagnoses."
    ),
    QueryType.DRUG_DEEP_DIVE: (
        _BASE_SYSTEM + "\n\nThe user wants detail on a single drug. "
        "Retrieve Drug Interactions, Warnings, and Adverse Reactions label sections."
    ),
    QueryType.GENERAL_QUESTION: _BASE_SYSTEM,
}


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    from guardrails.input_guards import run_input_guards
    from guardrails.output_guards import apply_output_guards
    from models.analysis import AnalysisResult as AR
    from models.medication import Medication as Med
    from tools.normalizer import normalize_medications, normalize_medication
    from tools.interaction_checker import calculate_interaction_matrix, check_interaction_pair
    from orchestrator.briefing_generator import generate_briefing
    from rag.retriever import retrieve

    match name:
        case "normalize_medications":
            guard = run_input_guards(args["raw_input"])
            if guard.blocked:
                return {"blocked": True, "message": guard.message}
            meds = await normalize_medications(guard.cleaned_text)
            return [m.model_dump() for m in meds]

        case "calculate_interaction_matrix":
            meds = [Med.model_validate(m) for m in args["medications"]]
            result = await calculate_interaction_matrix(meds)
            result.interactions = apply_output_guards(result.interactions)
            return result.model_dump()

        case "generate_briefing":
            ar = AR.model_validate(args["analysis_result"])
            briefing = await generate_briefing(ar)
            return briefing.model_dump()

        case "get_drug_label":
            section = args.get("section", "Drug Interactions")
            results = await retrieve(
                query=f"{section} information",
                rxcui_a=args["rxcui"],
                top_k=3,
            )
            filtered = [r for r in results if r.section_type == section] or results
            return {"sections": [{"text": r.text, "setid": r.setid} for r in filtered[:3]]}

        case "add_drug_check":
            guard = run_input_guards(args["new_drug"])
            if guard.blocked:
                return {"blocked": True, "message": guard.message}
            existing = [Med.model_validate(m) for m in args["existing_medications"]]
            new_med = await normalize_medication(guard.cleaned_text)
            from tools.interaction_checker import check_interaction_pair as cip  # noqa: PLC0415
            new_interactions = list(await __import__("asyncio").gather(
                *[cip(new_med, m) for m in existing]
            ))
            new_interactions = apply_output_guards(new_interactions)
            return {
                "new_medication": new_med.model_dump(),
                "new_interactions": [i.model_dump() for i in new_interactions],
            }

        case "check_interaction_pair":
            med_a = Med.model_validate(args["med_a"])
            med_b = Med.model_validate(args["med_b"])
            ix = await check_interaction_pair(med_a, med_b)
            return ix.model_dump()

        case "get_adverse_events":
            # Stub — Week 5
            return {"drug_name": args["drug_name"], "reports": [], "data_sparse": True}

        case _:
            return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Agentic replanning
# ---------------------------------------------------------------------------

async def _maybe_replan(
    tool_results: list[dict],
    messages: list[dict],
    query_type: QueryType,
) -> list[str]:
    """Return additional guidance messages when thin-data conditions are detected."""
    hints: list[str] = []

    for tr in tool_results:
        content = tr.get("content", {})
        if isinstance(content, list):
            # normalize result — check confidence
            for med in content:
                if isinstance(med, dict) and med.get("confidence", 1.0) < 0.7:
                    hints.append(
                        f"Note: '{med.get('input_text')}' was normalised with low confidence "
                        f"({med.get('confidence'):.0%}). Consider asking the user to clarify the drug name."
                    )
        if isinstance(content, dict):
            # Empty RAG or sparse data
            sections = content.get("sections", [])
            if sections == []:
                hints.append(
                    "The label retrieval returned no results. "
                    "Try widening the search to the drug class rather than the specific drug name."
                )
            # Supplement gap
            if content.get("type") == "supplement" and not content.get("rxcui"):
                name = content.get("name", "this supplement")
                hints.append(
                    f"{name} is not in RxNorm. Try searching for its active compound "
                    f"({', '.join(content.get('active_compounds', ['unknown']))}) instead."
                )

    return hints


# ---------------------------------------------------------------------------
# Main orchestrator loop
# ---------------------------------------------------------------------------

async def run(
    query_type: QueryType,
    user_input: str,
    session_medications: list[Medication] | None = None,
) -> dict[str, Any]:
    client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    system = _SYSTEM_BY_TYPE.get(query_type, _BASE_SYSTEM)

    initial_content = user_input
    if session_medications:
        med_list = ", ".join(m.name for m in session_medications)
        initial_content = f"Current medications: {med_list}\n\n{user_input}"

    messages: list[dict] = [{"role": "user", "content": initial_content}]

    for turn in range(MAX_TURNS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOLS,  # type: ignore[arg-type]
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text = next(
                (b.text for b in response.content if hasattr(b, "text")),
                "Analysis complete.",
            )
            return {"type": "text", "content": text, "query_type": query_type.value}

        # Collect tool calls
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            break

        messages.append({"role": "assistant", "content": response.content})

        tool_results: list[dict] = []
        for block in tool_use_blocks:
            try:
                result = await _dispatch(block.name, block.input)
                content_str = json.dumps(result, default=str)
            except Exception as exc:
                logger.warning("Tool %s failed: %s", block.name, exc)
                content_str = json.dumps({"error": str(exc)})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content_str,
            })

        # Agentic replanning hints
        hints = await _maybe_replan(
            [{"content": json.loads(tr["content"])} for tr in tool_results],
            messages,
            query_type,
        )

        user_content: list = list(tool_results)
        if hints:
            user_content.append({"type": "text", "text": "\n".join(hints)})

        messages.append({"role": "user", "content": user_content})

    return {"type": "error", "content": "Orchestrator did not reach a conclusion.", "query_type": query_type.value}
