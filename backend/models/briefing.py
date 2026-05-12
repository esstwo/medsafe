from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from models.medication import Medication
from models.interaction import Interaction


class Citation(BaseModel):
    source_type: str
    source_id: str
    title: str | None = None
    url: str | None = None
    section: str | None = None


class Attribution(BaseModel):
    symptom: str
    drug_name: str
    rxcui: str | None = None
    likelihood: str
    evidence_summary: str
    source: Citation | None = None


class FAERSResult(BaseModel):
    drug_name: str
    rxcui: str | None = None
    total_reports: int
    serious_outcomes: int
    top_reactions: list[str] = Field(default_factory=list)
    data_sparse: bool = False


class SafetyBriefing(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    medications: list[Medication] = Field(default_factory=list)
    interactions: list[Interaction] = Field(default_factory=list)
    symptom_attributions: list[Attribution] | None = None
    adverse_events: list[FAERSResult] | None = None
    provider_questions: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "This information is for educational purposes only and does not constitute medical advice. "
        "Always consult your healthcare provider before making any changes to your medications."
    )
    sources: list[Citation] = Field(default_factory=list)
