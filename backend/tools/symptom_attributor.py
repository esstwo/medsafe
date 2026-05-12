"""Symptom attribution — RAG over Adverse Reactions + Claude classification."""

from __future__ import annotations

import asyncio
import json
import logging
import re

import anthropic

from app.config import get_settings
from models.briefing import Attribution, Citation
from models.medication import Medication
from rag.retriever import retrieve

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are a clinical pharmacovigilance assistant. Determine whether a reported symptom "
    "is consistent with known adverse reactions from a patient's medications.\n"
    "Rules:\n"
    "- Frame all findings as hypotheses — never as diagnoses.\n"
    "- Never recommend changing, stopping, or starting medications.\n"
    "- If the symptom appears in multiple drugs' adverse reaction profiles, list all.\n"
    "- If no drug in the list is known to cause the symptom, say so explicitly.\n"
    "Respond with a JSON object only — no surrounding text."
)

_USER_TEMPLATE = """\
Patient medications: {med_list}
Reported symptom: "{symptom}"

FDA label Adverse Reactions data retrieved:
{context}

Return JSON:
{{
  "attributed_to": "<drug_name>" | null,
  "likelihood": "probable" | "possible" | "unlikely" | "unknown",
  "evidence_summary": "<1-2 sentence clinical explanation citing the label data>",
  "secondary_drugs": ["<other_drug_name>"]
}}"""


async def _retrieve_adverse_reactions(
    symptom: str, medications: list[Medication]
) -> tuple[str, str | None]:
    """Return (aggregated_text, top_setid) from Adverse Reactions sections."""
    all_results = []
    for med in medications:
        # Include drug name in query so BM25 finds relevant sections even if rxcui mismatches
        results = await retrieve(
            query=f"{med.name} {symptom} adverse reaction side effect",
            rxcui_a=med.rxcui or None,
            top_k=3,
        )
        # If rxcui-filtered search returned nothing, retry without rxcui filter using drug name
        if not results:
            results = await retrieve(
                query=f"{med.name} adverse reactions {symptom}",
                top_k=2,
            )
        filtered = [r for r in results if r.section_type == "Adverse Reactions"] or results[:1]
        for r in filtered:
            all_results.append((med.name, r))

    if not all_results:
        return "", None

    parts: list[str] = []
    top_setid: str | None = None
    for drug_name, result in all_results[:6]:  # cap total context
        parts.append(f"[{drug_name} — {result.section_type or 'Adverse Reactions'}]:\n{result.text[:400]}")
        if top_setid is None:
            top_setid = result.setid

    return "\n\n".join(parts)[:3000], top_setid


async def _attribute_single(
    symptom: str,
    medications: list[Medication],
) -> Attribution | None:
    med_list = ", ".join(m.name for m in medications)
    context, top_setid = await _retrieve_adverse_reactions(symptom, medications)

    if not context:
        return Attribution(
            symptom=symptom,
            drug_name="unknown",
            likelihood="unknown",
            evidence_summary=(
                f"No FDA label adverse reaction data was found for '{symptom}' "
                "in the retrieved corpus. This does not mean there is no association."
            ),
        )

    user_msg = _USER_TEMPLATE.format(
        med_list=med_list,
        symptom=symptom,
        context=context,
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
        response = await client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("Symptom attribution Claude call failed for '%s': %s", symptom, exc)
        return Attribution(
            symptom=symptom,
            drug_name="unknown",
            likelihood="unknown",
            evidence_summary="Attribution analysis could not be completed. Please consult your pharmacist.",
        )

    attributed_drug = data.get("attributed_to")
    likelihood = data.get("likelihood", "unknown")

    # Look up rxcui for the attributed drug
    rxcui: str | None = None
    if attributed_drug:
        for med in medications:
            if med.name.lower() == attributed_drug.lower():
                rxcui = med.rxcui
                break

    source: Citation | None = None
    if top_setid and attributed_drug:
        source = Citation(
            source_type="fda_label",
            source_id=top_setid,
            title=f"FDA Drug Label — Adverse Reactions ({attributed_drug})",
            section="Adverse Reactions",
        )

    return Attribution(
        symptom=symptom,
        drug_name=attributed_drug or "unknown",
        rxcui=rxcui,
        likelihood=likelihood,
        evidence_summary=data.get("evidence_summary", ""),
        source=source,
    )


async def attribute_symptoms(
    symptoms: list[str],
    medications: list[Medication],
) -> list[Attribution]:
    """Attribute each symptom to a likely medication via RAG + Claude."""
    if not symptoms or not medications:
        return []

    results = await asyncio.gather(*[_attribute_single(s, medications) for s in symptoms])
    return [r for r in results if r is not None]
