from typing import Literal
from pydantic import BaseModel


class RetrievalResult(BaseModel):
    text: str
    source_type: Literal["dailymed_label", "drugbank_interaction"]
    rxcui: str | None = None
    section_type: str | None = None   # "Drug Interactions", "Warnings", etc.
    drug_name: str | None = None
    severity: str | None = None       # populated for drugbank_interaction results
    score: float = 0.0                # RRF score or reranker score
    setid: str | None = None          # DailyMed setid — used for citations
    drugbank_id: str | None = None
