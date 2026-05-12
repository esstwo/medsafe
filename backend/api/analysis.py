from fastapi import APIRouter
from pydantic import BaseModel

from guardrails.output_guards import apply_output_guards
from models.analysis import AnalysisResult
from models.medication import Medication
from tools.interaction_checker import calculate_interaction_matrix

router = APIRouter()


class AnalysisRequest(BaseModel):
    medications: list[Medication]
    session_id: str = ""


@router.post("/full", response_model=AnalysisResult)
async def full_analysis(req: AnalysisRequest) -> AnalysisResult:
    if len(req.medications) < 2:
        return AnalysisResult(
            session_id=req.session_id or None,
            medications=req.medications,
            interactions=[],
        )

    result = await calculate_interaction_matrix(req.medications)
    if req.session_id:
        result.session_id = req.session_id
    result.interactions = apply_output_guards(result.interactions)
    return result
