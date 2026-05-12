from fastapi import APIRouter
from pydantic import BaseModel

from models.analysis import AnalysisResult
from models.briefing import SafetyBriefing
from orchestrator.briefing_generator import generate_briefing

router = APIRouter()


class BriefingRequest(BaseModel):
    analysis_result: AnalysisResult


@router.post("/generate", response_model=SafetyBriefing)
async def generate(req: BriefingRequest) -> SafetyBriefing:
    return await generate_briefing(req.analysis_result)
