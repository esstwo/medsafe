from typing import Literal
from pydantic import BaseModel

from models.medication import Medication


class InteractionSource(BaseModel):
    type: Literal["drugbank", "fda_label", "faers"]
    id: str
    section: str | None = None
    url: str | None = None


class Interaction(BaseModel):
    drug_a: Medication
    drug_b: Medication
    severity: Literal["major", "moderate", "minor", "unknown"]
    mechanism: str | None = None
    mechanism_plain: str | None = None
    clinical_effect: str | None = None
    evidence_level: Literal["well-documented", "theoretical", "case-reports"] | None = None
    source: InteractionSource | None = None
    confidence: Literal["high", "moderate", "low"] | None = None
