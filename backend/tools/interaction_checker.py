"""
Interaction checker — shared core used by FastAPI routes (Week 3) and MCP tools (Week 4).

check_interaction_pair:  Supabase exact lookup → RAG retrieval → Claude extraction
calculate_interaction_matrix:  all N*(N-1)/2 pairs, async, concurrency-limited
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import anthropic

from app.config import get_settings
from db.client import get_pool
from db.interactions import lookup_interaction
from models.interaction import Interaction, InteractionSource
from models.medication import Medication
from models.analysis import AnalysisResult
from rag.retriever import retrieve

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# High-risk drug detection
# ---------------------------------------------------------------------------

_HIGH_RISK_NAMES = {
    # Anticoagulants
    "warfarin", "heparin", "enoxaparin", "rivaroxaban", "apixaban", "dabigatran",
    # MAOIs
    "phenelzine", "tranylcypromine", "isocarboxazid", "selegiline", "rasagiline",
    # SSRIs / SNRIs (serotonin syndrome risk)
    "fluoxetine", "sertraline", "escitalopram", "citalopram", "paroxetine",
    "venlafaxine", "duloxetine", "fluvoxamine",
    # TCAs
    "amitriptyline", "nortriptyline", "imipramine", "clomipramine",
    # Antipsychotics
    "haloperidol", "clozapine", "quetiapine", "olanzapine", "risperidone", "ziprasidone",
    # Benzodiazepines
    "alprazolam", "clonazepam", "lorazepam", "diazepam", "midazolam",
    # Opioids
    "morphine", "oxycodone", "hydrocodone", "codeine", "fentanyl",
    "methadone", "buprenorphine", "hydromorphone", "oxymorphone", "tramadol",
    # Narrow therapeutic index
    "digoxin", "lithium", "phenytoin", "carbamazepine", "valproate", "valproic acid",
    "theophylline", "cyclosporine", "tacrolimus", "methotrexate", "warfarin",
    # Immunosuppressants / chemo
    "azathioprine", "cyclophosphamide", "mercaptopurine",
}

_HIGH_RISK_SUFFIX = (
    " Note: this combination involves at least one medication with a narrow margin of safety "
    "or high interaction risk. Discuss with your prescriber or pharmacist before making any changes."
)


def _is_high_risk(med: Medication) -> bool:
    return med.name.lower() in _HIGH_RISK_NAMES


# ---------------------------------------------------------------------------
# Claude client
# ---------------------------------------------------------------------------

_claude: anthropic.AsyncAnthropic | None = None

MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are a clinical pharmacology assistant. Analyse FDA drug label text to identify "
    "interactions between two drugs. Rules:\n"
    "- Never recommend starting, stopping, or changing any medication.\n"
    "- Always frame findings as information, not medical advice.\n"
    "- State uncertainty explicitly when evidence is limited.\n"
    "- Respond with a JSON object only — no surrounding text, no markdown fences."
)

_USER_TEMPLATE = """\
Drug A: {name_a} (RXCUI: {rxcui_a})
Drug B: {name_b} (RXCUI: {rxcui_b})

{context_section}

Return JSON with exactly these keys:
{{
  "has_interaction": <bool>,
  "severity": "major" | "moderate" | "minor" | "unknown",
  "mechanism": "<clinical mechanism, 1-2 sentences or null>",
  "mechanism_plain": "<plain English explanation, no jargon, 1-2 sentences or null>",
  "clinical_effect": "<what may happen clinically, 1 sentence or null>",
  "evidence_level": "well-documented" | "theoretical" | "case-reports" | "unknown"
}}"""


def _get_claude() -> anthropic.AsyncAnthropic:
    global _claude
    if _claude is None:
        _claude = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _claude


async def _claude_extract(
    med_a: Medication,
    med_b: Medication,
    context: str,
) -> dict[str, Any]:
    """Call Claude to extract structured interaction data from retrieved context."""
    user_msg = _USER_TEMPLATE.format(
        name_a=med_a.name,
        rxcui_a=med_a.rxcui or "unknown",
        name_b=med_b.name,
        rxcui_b=med_b.rxcui or "unknown",
        context_section=context,
    )
    client = _get_claude()
    message = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = message.content[0].text.strip()
    # Strip any accidental markdown fences
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def _build_interaction(
    med_a: Medication,
    med_b: Medication,
    extracted: dict[str, Any],
    source: InteractionSource | None,
    supabase_severity: str | None = None,
) -> Interaction:
    severity = supabase_severity or extracted.get("severity", "unknown")
    # Validate severity is in allowed set
    if severity not in {"major", "moderate", "minor", "unknown"}:
        severity = "unknown"

    mechanism_plain = extracted.get("mechanism_plain")
    if mechanism_plain and (_is_high_risk(med_a) or _is_high_risk(med_b)):
        mechanism_plain = mechanism_plain.rstrip(".") + "." + _HIGH_RISK_SUFFIX

    evidence_level = extracted.get("evidence_level", "unknown")
    if evidence_level not in {"well-documented", "theoretical", "case-reports", "unknown"}:
        evidence_level = None

    confidence: str
    if supabase_severity and supabase_severity != "unknown":
        confidence = "high"
    elif extracted.get("has_interaction"):
        confidence = "moderate"
    else:
        confidence = "low"

    return Interaction(
        drug_a=med_a,
        drug_b=med_b,
        severity=severity,  # type: ignore[arg-type]
        mechanism=extracted.get("mechanism"),
        mechanism_plain=mechanism_plain,
        clinical_effect=extracted.get("clinical_effect"),
        evidence_level=evidence_level,  # type: ignore[arg-type]
        source=source,
        confidence=confidence,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Main pair checker
# ---------------------------------------------------------------------------

async def check_interaction_pair(med_a: Medication, med_b: Medication) -> Interaction:
    """
    1. Supabase exact lookup  → if severity known, enrich with Claude and return
    2. RAG retrieval          → filter to Drug Interactions sections
    3. Claude extraction      → structured Interaction
    """
    rxcui_a = med_a.rxcui or ""
    rxcui_b = med_b.rxcui or ""

    # ------------------------------------------------------------------
    # Step 1: Supabase fast path
    # ------------------------------------------------------------------
    supabase_row: dict | None = None
    if rxcui_a and rxcui_b:
        try:
            pool = await get_pool()
            supabase_row = await lookup_interaction(pool, rxcui_a, rxcui_b)
        except Exception as exc:
            logger.warning("Supabase lookup failed for %s+%s: %s", med_a.name, med_b.name, exc)

    if supabase_row and supabase_row.get("severity") not in (None, "unknown"):
        description = supabase_row.get("description", "")
        drugbank_id = supabase_row.get("drugbank_id", "")
        source = InteractionSource(
            type="drugbank",
            id=drugbank_id or f"{rxcui_a}-{rxcui_b}",
        )
        context = (
            f"Known interaction description from DrugBank:\n{description}"
            if description
            else "Interaction is recorded but no description is available."
        )
        try:
            extracted = await _claude_extract(med_a, med_b, context)
        except Exception as exc:
            logger.warning("Claude enrichment failed for %s+%s: %s", med_a.name, med_b.name, exc)
            # Fallback: minimal Interaction from Supabase data alone
            return Interaction(
                drug_a=med_a,
                drug_b=med_b,
                severity=supabase_row["severity"],  # type: ignore[arg-type]
                mechanism=description or None,
                mechanism_plain=description or None,
                source=source,
                confidence="high",
            )
        return _build_interaction(
            med_a, med_b, extracted, source,
            supabase_severity=supabase_row["severity"],
        )

    # ------------------------------------------------------------------
    # Step 2: RAG retrieval
    # ------------------------------------------------------------------
    query = f"{med_a.name} {med_b.name} drug interaction"
    rag_results = []
    try:
        rag_results = await retrieve(query=query, rxcui_a=rxcui_a or None, rxcui_b=rxcui_b or None, top_k=5)
    except Exception as exc:
        logger.warning("RAG retrieval failed for %s+%s: %s", med_a.name, med_b.name, exc)

    # Prefer Drug Interactions sections; fall back to any result
    di_results = [r for r in rag_results if r.section_type == "Drug Interactions"]
    best_results = di_results or rag_results

    if not best_results:
        return Interaction(
            drug_a=med_a,
            drug_b=med_b,
            severity="unknown",
            mechanism_plain=(
                f"No interaction data found for {med_a.name} and {med_b.name} "
                "in the available FDA label corpus. Absence of data does not confirm safety."
            ),
            confidence="low",
        )

    # ------------------------------------------------------------------
    # Step 3: Claude extraction from RAG text
    # ------------------------------------------------------------------
    combined_text = "\n\n---\n\n".join(r.text for r in best_results[:3])
    combined_text = combined_text[:3000]  # cap context window

    setid = best_results[0].setid if best_results else None
    section = best_results[0].section_type if best_results else None
    source = InteractionSource(
        type="fda_label",
        id=setid or f"{rxcui_a}-{rxcui_b}",
        section=section,
    )

    context = f"FDA label sections retrieved:\n{combined_text}"
    try:
        extracted = await _claude_extract(med_a, med_b, context)
    except Exception as exc:
        logger.warning("Claude extraction failed for %s+%s: %s", med_a.name, med_b.name, exc)
        return Interaction(
            drug_a=med_a,
            drug_b=med_b,
            severity="unknown",
            mechanism_plain="Interaction analysis could not be completed. Please consult your pharmacist.",
            confidence="low",
        )

    if not extracted.get("has_interaction"):
        return Interaction(
            drug_a=med_a,
            drug_b=med_b,
            severity="unknown",
            mechanism_plain=(
                f"No clinically significant interaction between {med_a.name} and {med_b.name} "
                "was identified in the retrieved FDA label text. "
                "Absence of data does not confirm safety."
            ),
            confidence="low",
        )

    return _build_interaction(med_a, med_b, extracted, source)


# ---------------------------------------------------------------------------
# Interaction matrix
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"major": 0, "moderate": 1, "minor": 2, "unknown": 3}


async def calculate_interaction_matrix(medications: list[Medication]) -> AnalysisResult:
    pairs = [
        (medications[i], medications[j])
        for i in range(len(medications))
        for j in range(i + 1, len(medications))
    ]

    sem = asyncio.Semaphore(3)

    async def _checked(med_a: Medication, med_b: Medication) -> Interaction:
        async with sem:
            return await check_interaction_pair(med_a, med_b)

    interactions = list(
        await asyncio.gather(*[_checked(a, b) for a, b in pairs])
    )

    interactions.sort(key=lambda i: _SEVERITY_ORDER.get(i.severity, 3))

    return AnalysisResult(medications=medications, interactions=interactions)
