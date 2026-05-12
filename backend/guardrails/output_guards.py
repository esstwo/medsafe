import logging
import re

from models.interaction import Interaction

logger = logging.getLogger(__name__)

_PRESCRIBING_PATTERNS = re.compile(
    r"\b(you should (take|stop|start|increase|decrease|avoid|not take)|"
    r"do not take|stop taking|start taking|switch to|replace with|"
    r"you need to (take|stop|start)|discontinue|must not take)\b",
    re.IGNORECASE,
)

_REDIRECT = (
    " Please discuss any medication changes with your healthcare provider "
    "before making adjustments."
)


def check_prescribing_language(text: str) -> str:
    """Detect prescribing language and append a provider-redirect if found."""
    if _PRESCRIBING_PATTERNS.search(text):
        logger.warning("Prescribing language detected in output — appending redirect.")
        if _REDIRECT.strip() not in text:
            return text.rstrip() + _REDIRECT
    return text


def check_citation(interaction: Interaction) -> bool:
    """Return True if the interaction has a traceable source or explicitly notes no data."""
    no_data_note = "no interaction data found" in (interaction.mechanism_plain or "").lower()
    return interaction.source is not None or no_data_note or interaction.severity == "unknown"


def apply_output_guards(interactions: list[Interaction]) -> list[Interaction]:
    """Apply all output guardrails in-place. Returns the same list."""
    for ix in interactions:
        if ix.mechanism_plain:
            ix.mechanism_plain = check_prescribing_language(ix.mechanism_plain)
        if not check_citation(ix):
            logger.warning(
                "Interaction %s+%s has no source citation — flagged for review.",
                ix.drug_a.name,
                ix.drug_b.name,
            )
    return interactions
