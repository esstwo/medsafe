from fastapi import APIRouter
from pydantic import BaseModel

from models.analysis import AnalysisResult
from models.briefing import SafetyBriefing
from orchestrator.briefing_generator import generate_briefing

router = APIRouter()


class BriefingRequest(BaseModel):
    analysis_result: AnalysisResult
    symptoms: list[str] | None = None
    include_faers: bool = True


@router.post("/generate", response_model=SafetyBriefing)
async def generate(req: BriefingRequest) -> SafetyBriefing:
    return await generate_briefing(
        req.analysis_result,
        symptoms=req.symptoms,
        include_faers=req.include_faers,
    )
