import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from guardrails.input_guards import run_input_guards
from guardrails.output_guards import apply_output_guards
from models.analysis import AnalysisResult
from models.briefing import Attribution
from models.interaction import Interaction
from models.medication import Medication
from tools.interaction_checker import calculate_interaction_matrix, check_interaction_pair
from tools.normalizer import normalize_medication
from tools.symptom_attributor import attribute_symptoms

router = APIRouter()


class AnalysisRequest(BaseModel):
    medications: list[Medication]
    session_id: str = ""


class AddDrugRequest(BaseModel):
    existing_medications: list[Medication]
    new_drug: str
    session_id: str = ""


class AddDrugResponse(BaseModel):
    new_medication: Medication
    new_interactions: list[Interaction]


class SymptomsRequest(BaseModel):
    symptoms: list[str]
    medications: list[Medication]
    session_id: str = ""


class AttributionResponse(BaseModel):
    attributions: list[Attribution]


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


@router.post("/add-drug", response_model=AddDrugResponse)
async def add_drug(req: AddDrugRequest) -> AddDrugResponse:
    guard = run_input_guards(req.new_drug)
    if guard.blocked:
        # Return as a safe empty response rather than an error — the UI shows the guardrail message
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={"blocked": True, "message": guard.message, "action": guard.action},
        )

    new_med = await normalize_medication(guard.cleaned_text)
    new_interactions: list[Interaction] = list(
        await asyncio.gather(*[check_interaction_pair(new_med, m) for m in req.existing_medications])
    )
    new_interactions = apply_output_guards(new_interactions)

    return AddDrugResponse(new_medication=new_med, new_interactions=new_interactions)


@router.post("/symptoms", response_model=AttributionResponse)
async def symptoms_endpoint(req: SymptomsRequest) -> AttributionResponse:
    if not req.symptoms or not req.medications:
        return AttributionResponse(attributions=[])
    attributions = await attribute_symptoms(req.symptoms, req.medications)
    return AttributionResponse(attributions=attributions)
