import logging
import re
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_EMERGENCY_PHRASES = [
    "overdose",
    "too many pills",
    "took all my",
    "took too many",
    "want to die",
    "kill myself",
    "end my life",
    "poison control",
    "can't breathe",
    "cannot breathe",
    "chest pain",
    "having a heart attack",
    "allergic reaction",
    "stop breathing",
    "unconscious",
    "passed out",
]

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_DOB_RE = re.compile(r"\b(0?[1-9]|1[0-2])[/\-](0?[1-9]|[12]\d|3[01])[/\-](\d{4}|\d{2})\b")
_INSURANCE_RE = re.compile(r"\b[A-Z]{2,3}\d{6,12}\b")


class GuardrailResult(BaseModel):
    blocked: bool
    cleaned_text: str
    message: str | None = None
    action: str | None = None


def check_emergency(text: str) -> GuardrailResult:
    lower = text.lower()
    for phrase in _EMERGENCY_PHRASES:
        if phrase in lower:
            return GuardrailResult(
                blocked=True,
                cleaned_text=text,
                message=(
                    "It sounds like you may be experiencing a medical emergency. "
                    "Please call 911 or Poison Control at 1-800-222-1222 immediately. "
                    "MedSafe cannot provide emergency medical guidance."
                ),
                action="emergency",
            )
    return GuardrailResult(blocked=False, cleaned_text=text)


def strip_pii(text: str) -> str:
    result = text
    had_pii = False

    if _SSN_RE.search(result):
        result = _SSN_RE.sub("[REDACTED]", result)
        had_pii = True

    if _DOB_RE.search(result):
        result = _DOB_RE.sub("[REDACTED]", result)
        had_pii = True

    if _INSURANCE_RE.search(result):
        result = _INSURANCE_RE.sub("[REDACTED]", result)
        had_pii = True

    if had_pii:
        logger.warning("PII detected and stripped from input")

    return result


def run_input_guards(text: str) -> GuardrailResult:
    emergency = check_emergency(text)
    if emergency.blocked:
        return emergency

    cleaned = strip_pii(text)
    return GuardrailResult(blocked=False, cleaned_text=cleaned)
