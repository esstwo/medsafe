from pydantic import BaseModel, Field
import uuid

from models.medication import Medication
from models.interaction import Interaction


class AnalysisResult(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    medications: list[Medication] = Field(default_factory=list)
    interactions: list[Interaction] = Field(default_factory=list)
