import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from guardrails.input_guards import run_input_guards
from models.medication import Medication
from tools.normalizer import normalize_medications

router = APIRouter()


class NormalizeRequest(BaseModel):
    medications: str


class NormalizeResponse(BaseModel):
    blocked: bool = False
    message: str | None = None
    medications: list[Medication] = []
    warnings: list[str] = []


class ConfirmRequest(BaseModel):
    medications: list[Medication]


class ConfirmResponse(BaseModel):
    medications: list[Medication]
    session_id: str


@router.post("/normalize", response_model=NormalizeResponse)
async def normalize(req: NormalizeRequest) -> NormalizeResponse:
    if not req.medications.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://medsafe.dev/errors/empty-input",
                "title": "Empty input",
                "status": 400,
                "detail": "medications field must not be empty",
            },
        )

    guard = run_input_guards(req.medications)
    if guard.blocked:
        return NormalizeResponse(blocked=True, message=guard.message)

    medications = await normalize_medications(guard.cleaned_text)

    warnings: list[str] = []
    for med in medications:
        if med.confidence < 0.5:
            warnings.append(
                f"Could not confidently identify '{med.input_text}'. "
                "Please verify the drug name or consult your pharmacist."
            )
        elif med.confidence < 0.7 and med.type == "supplement":
            warnings.append(
                f"'{med.input_text}' resolved as a supplement with limited data. "
                "Evidence for interactions may be sparse."
            )

    return NormalizeResponse(medications=medications, warnings=warnings)


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm(req: ConfirmRequest) -> ConfirmResponse:
    if not req.medications:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://medsafe.dev/errors/empty-medication-list",
                "title": "Empty medication list",
                "status": 400,
                "detail": "At least one medication is required",
            },
        )
    return ConfirmResponse(
        medications=req.medications,
        session_id=str(uuid.uuid4()),
    )
