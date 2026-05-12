"""MCP tool definitions — thin wrappers over shared-core functions."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent


def register_tools(server: Server) -> None:

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="normalize_medications",
                description=(
                    "Resolve free-text drug or supplement names to structured Medication objects "
                    "via RxNorm. Handles brand names, generics, and common supplements."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "medications": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of drug/supplement names as free text",
                        }
                    },
                    "required": ["medications"],
                },
            ),
            Tool(
                name="check_interactions",
                description=(
                    "Compute all pairwise drug interactions for a confirmed medication list. "
                    "Returns Interaction objects sorted major→moderate→minor→unknown."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "medications": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of Medication objects from normalize_medications",
                        }
                    },
                    "required": ["medications"],
                },
            ),
            Tool(
                name="generate_briefing",
                description=(
                    "Synthesise an analysis result into a full SafetyBriefing with "
                    "auto-generated provider questions and source citations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "analysis_result": {
                            "type": "object",
                            "description": "AnalysisResult object from check_interactions",
                        }
                    },
                    "required": ["analysis_result"],
                },
            ),
            Tool(
                name="get_drug_label",
                description="Retrieve a specific FDA label section for a drug by RXCUI.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "rxcui": {"type": "string", "description": "RxNorm RXCUI for the drug"},
                        "section": {
                            "type": "string",
                            "enum": ["Drug Interactions", "Warnings", "Contraindications", "Adverse Reactions"],
                            "default": "Drug Interactions",
                        },
                    },
                    "required": ["rxcui"],
                },
            ),
            Tool(
                name="add_drug_check",
                description=(
                    "Check a new drug against an existing confirmed medication list. "
                    "Returns only the new interaction pairs — does not recompute existing pairs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "existing_medications": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Already-confirmed Medication objects",
                        },
                        "new_drug": {"type": "string", "description": "Name of the drug to add"},
                    },
                    "required": ["existing_medications", "new_drug"],
                },
            ),
            Tool(
                name="get_adverse_events",
                description="Get FAERS adverse event data for a drug (stub — full data in Week 5).",
                inputSchema={
                    "type": "object",
                    "properties": {"drug_name": {"type": "string"}},
                    "required": ["drug_name"],
                },
            ),
            Tool(
                name="attribute_symptoms",
                description="Attribute reported symptoms to drugs in the medication list using FDA label adverse reaction data.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symptoms": {"type": "array", "items": {"type": "string"}},
                        "medications": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["symptoms", "medications"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]


async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    from guardrails.input_guards import run_input_guards
    from guardrails.output_guards import apply_output_guards
    from models.analysis import AnalysisResult
    from models.medication import Medication
    from tools.normalizer import normalize_medications, normalize_medication
    from tools.interaction_checker import calculate_interaction_matrix, check_interaction_pair
    from orchestrator.briefing_generator import generate_briefing
    from rag.retriever import retrieve

    match name:
        case "normalize_medications":
            raw = ", ".join(args["medications"])
            guard = run_input_guards(raw)
            if guard.blocked:
                return {"blocked": True, "message": guard.message}
            meds = await normalize_medications(guard.cleaned_text)
            return [m.model_dump() for m in meds]

        case "check_interactions":
            meds = [Medication.model_validate(m) for m in args["medications"]]
            result = await calculate_interaction_matrix(meds)
            result.interactions = apply_output_guards(result.interactions)
            return result.model_dump()

        case "generate_briefing":
            ar = AnalysisResult.model_validate(args["analysis_result"])
            briefing = await generate_briefing(ar)
            return briefing.model_dump()

        case "get_drug_label":
            section = args.get("section", "Drug Interactions")
            results = await retrieve(
                query=f"{section}",
                rxcui_a=args["rxcui"],
                top_k=3,
            )
            filtered = [r for r in results if r.section_type == section] or results
            return {
                "rxcui": args["rxcui"],
                "section": section,
                "content": [{"text": r.text, "setid": r.setid, "score": r.score} for r in filtered[:3]],
            }

        case "add_drug_check":
            guard = run_input_guards(args["new_drug"])
            if guard.blocked:
                return {"blocked": True, "message": guard.message}
            existing = [Medication.model_validate(m) for m in args["existing_medications"]]
            new_med = await normalize_medication(guard.cleaned_text)
            interactions = list(await asyncio.gather(*[check_interaction_pair(new_med, m) for m in existing]))
            interactions = apply_output_guards(interactions)
            return {
                "new_medication": new_med.model_dump(),
                "new_interactions": [i.model_dump() for i in interactions],
            }

        case "get_adverse_events":
            from tools.openfda import get_faers_data
            result = await get_faers_data(args["drug_name"], rxcui=args.get("rxcui"))
            return result.model_dump()

        case "attribute_symptoms":
            from tools.symptom_attributor import attribute_symptoms as _attr
            meds = [Medication.model_validate(m) for m in args["medications"]]
            attributions = await _attr(args["symptoms"], meds)
            return [a.model_dump() for a in attributions]

        case _:
            return {"error": f"Unknown tool: {name}"}
