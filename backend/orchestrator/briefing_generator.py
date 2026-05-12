"""Safety briefing generator — synthesises AnalysisResult → SafetyBriefing."""

from __future__ import annotations

import logging
import os

import anthropic

from app.config import get_settings
from guardrails.output_guards import check_prescribing_language
from models.analysis import AnalysisResult
from models.briefing import Citation, SafetyBriefing
from models.interaction import Interaction

logger = logging.getLogger(__name__)

_QUESTIONS_PROMPT = """\
You are a patient advocate helping someone prepare for a conversation with their healthcare provider.

Based on the following medication list and flagged drug interactions, generate exactly 3 to 5 specific \
questions this patient should ask their doctor or pharmacist.

Rules:
- Questions must be information-seeking only — never recommend starting, stopping, or changing medications.
- Each question must be specific to the patient's actual medications and interactions listed.
- Frame questions as "Should I..." or "Is there..." or "How will you monitor..." — never as directives.
- Plain language only. No medical jargon.
- Output one question per line, no numbering, no bullets.

Medications: {med_list}

Flagged interactions:
{interaction_lines}"""


def _compile_sources(interactions: list[Interaction]) -> list[Citation]:
    seen: set[str] = set()
    citations: list[Citation] = []
    for ix in interactions:
        if ix.source is None:
            continue
        key = f"{ix.source.type}:{ix.source.id}"
        if key in seen:
            continue
        seen.add(key)
        label = (
            "DrugBank" if ix.source.type == "drugbank"
            else f"FDA Drug Label — {ix.source.section or 'Drug Interactions'}"
        )
        citations.append(Citation(
            source_type=ix.source.type,
            source_id=ix.source.id,
            title=label,
            section=ix.source.section,
            url=ix.source.url,
        ))
    return citations


async def _generate_provider_questions(
    analysis: AnalysisResult,
    flagged: list[Interaction],
) -> list[str]:
    if not flagged:
        return [
            "Should I schedule a medication review with my pharmacist?",
            "Are there any supplements or over-the-counter drugs I should avoid with my current medications?",
        ]

    med_list = ", ".join(m.name for m in analysis.medications)
    interaction_lines = "\n".join(
        f"- {ix.severity.upper()}: {ix.drug_a.name} + {ix.drug_b.name} — "
        f"{(ix.mechanism_plain or '').split('.')[0]}"
        for ix in flagged[:5]
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": _QUESTIONS_PROMPT.format(
                    med_list=med_list,
                    interaction_lines=interaction_lines,
                ),
            }],
        )
        raw = response.content[0].text.strip()
        questions = [check_prescribing_language(q.strip()) for q in raw.splitlines() if q.strip()]
        return questions[:5] or ["Please discuss these medication interactions with your healthcare provider."]
    except Exception as exc:
        logger.warning("Provider question generation failed: %s", exc)
        return [
            f"I have interactions flagged between {flagged[0].drug_a.name} and {flagged[0].drug_b.name} — "
            "what should I watch out for?",
            "Should any of these drug combinations be reviewed by a specialist?",
        ]


async def generate_briefing(analysis: AnalysisResult) -> SafetyBriefing:
    flagged = [ix for ix in analysis.interactions if ix.severity != "unknown"]
    sources = _compile_sources(analysis.interactions)
    provider_questions = await _generate_provider_questions(analysis, flagged)

    return SafetyBriefing(
        session_id=analysis.session_id,
        medications=analysis.medications,
        interactions=analysis.interactions,
        provider_questions=provider_questions,
        sources=sources,
        symptom_attributions=None,
        adverse_events=None,
    )


# LangSmith tracing — wraps generate_briefing if key is set
def _maybe_wrap_tracing() -> None:
    key = get_settings().langsmith_api_key
    if not key:
        return
    try:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", key)
        os.environ.setdefault("LANGCHAIN_PROJECT", "medsafe")
        from langsmith import traceable  # noqa: PLC0415
        global generate_briefing
        generate_briefing = traceable(run_type="chain", name="generate_briefing")(generate_briefing)
        logger.info("LangSmith tracing enabled for generate_briefing")
    except ImportError:
        pass


_maybe_wrap_tracing()
