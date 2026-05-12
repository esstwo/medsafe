"""Query type classifier for the FastAPI orchestrator path."""

from __future__ import annotations

import re
from enum import Enum

import anthropic

from app.config import get_settings

_SYMPTOM_WORDS = {
    "dizzy", "dizziness", "nausea", "nauseous", "pain", "headache", "tired",
    "fatigue", "rash", "itch", "bleed", "bleeding", "bruise", "swelling",
    "swollen", "stomach", "heartburn", "vomit", "diarrhea", "constipation",
    "fever", "chills", "anxious", "depressed", "confused", "memory",
    "i feel", "i've been", "i am feeling", "side effect", "side effects",
}

_ADD_WORDS = {"add", "adding", "can i take", "what about", "is it safe to add", "combine"}
_DEEPDIVE_WORDS = {"tell me about", "what is", "explain", "describe", "how does"}


class QueryType(str, Enum):
    FULL_ANALYSIS    = "FULL_ANALYSIS"
    INCREMENTAL_ADD  = "INCREMENTAL_ADD"
    SYMPTOM_CHECK    = "SYMPTOM_CHECK"
    DRUG_DEEP_DIVE   = "DRUG_DEEP_DIVE"
    GENERAL_QUESTION = "GENERAL_QUESTION"


def _heuristic_classify(user_input: str) -> QueryType | None:
    lower = user_input.lower()

    if any(w in lower for w in _ADD_WORDS):
        return QueryType.INCREMENTAL_ADD

    if any(w in lower for w in _SYMPTOM_WORDS):
        return QueryType.SYMPTOM_CHECK

    if any(w in lower for w in _DEEPDIVE_WORDS):
        return QueryType.DRUG_DEEP_DIVE

    # Plain drug list heuristic: mostly nouns, no verbs, comma/newline separated
    words = re.sub(r"[,\n]", " ", lower).split()
    if len(words) >= 2 and not any(
        w in lower for w in ("?", "what", "how", "why", "when", "is", "are", "do", "does")
    ):
        return QueryType.FULL_ANALYSIS

    return None


_CLASSIFY_PROMPT = """\
Classify this user input into exactly one query type for a drug safety advisor.

Query types:
- FULL_ANALYSIS: User wants to check all their current medications for interactions
- INCREMENTAL_ADD: User wants to add one new drug to an existing list
- SYMPTOM_CHECK: User is reporting a symptom and wants to know if it could be drug-related
- DRUG_DEEP_DIVE: User wants detailed information about a single drug
- GENERAL_QUESTION: Anything else (safety question, policy question, general info)

User input: {input}

Respond with only the query type name, nothing else."""


async def classify_query(
    user_input: str,
    session_medications: list[str] | None = None,
) -> QueryType:
    result = _heuristic_classify(user_input)
    if result is not None:
        return result

    # Fall back to Claude for ambiguous cases
    try:
        client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": _CLASSIFY_PROMPT.format(input=user_input),
            }],
        )
        label = response.content[0].text.strip().upper()
        return QueryType(label)
    except Exception:
        return QueryType.GENERAL_QUESTION
