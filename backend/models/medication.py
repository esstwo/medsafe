from typing import Literal
from pydantic import BaseModel, Field


class Medication(BaseModel):
    rxcui: str | None = None
    name: str
    brand_names: list[str] = Field(default_factory=list)
    input_text: str
    dose: str | None = None
    frequency: str | None = None
    type: Literal["prescription", "otc", "supplement"]
    confidence: float = Field(ge=0.0, le=1.0)
    active_compounds: list[str] = Field(default_factory=list)
