import asyncio
import re

from models.medication import Medication
from tools.rxnorm import (
    approximate_term,
    get_drug_info,
    lookup_supplement,
    is_known_otc,
)

_DOSE_RE = re.compile(
    r"(\d+\.?\d*)\s*(mg|mcg|ug|g\b|ml|iu|units?)",
    re.IGNORECASE,
)
_FREQ_RE = re.compile(
    r"\b(once|twice|qd|bid|tid|qid|daily|weekly|every\s+\d+\s+hours?|q\d+h)\b",
    re.IGNORECASE,
)
_STRIP_WORDS = re.compile(
    r"\b(baby|junior|children'?s?|adult|extra\s+strength|maximum\s+strength|regular\s+strength|"
    r"extended\s+release|er\b|xr\b|sr\b|delayed\s+release|dr\b|tablet|capsule|caplet|"
    r"softgel|gel\s+cap|liquid|syrup|suspension|solution|injection|patch|cream|ointment|"
    r"drops?|spray|inhaler|suppository|lozenge|chewable|sublingual)\b",
    re.IGNORECASE,
)


def _preprocess(raw: str) -> tuple[str, str | None, str | None]:
    """Strip dose/frequency from raw input; return (cleaned_name, dose, frequency)."""
    text = raw.strip()

    dose_match = _DOSE_RE.search(text)
    dose = f"{dose_match.group(1)} {dose_match.group(2)}" if dose_match else None
    if dose_match:
        text = text[: dose_match.start()] + text[dose_match.end() :]

    freq_match = _FREQ_RE.search(text)
    frequency = freq_match.group(0) if freq_match else None
    if freq_match:
        text = text[: freq_match.start()] + text[freq_match.end() :]

    text = _STRIP_WORDS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.")
    return text, dose, frequency


def _rxnorm_score_to_confidence(score: float) -> float:
    # RxNorm approximateTerm scores are floats roughly in the 0–20 range.
    # Exact and near-exact matches typically land at 10–15.
    if score >= 10.0:
        return 0.95
    if score >= 7.0:
        return 0.80
    if score >= 4.0:
        return 0.65
    return 0.0


async def normalize_medication(input_text: str) -> Medication:
    cleaned, dose, frequency = _preprocess(input_text)

    candidates = await approximate_term(cleaned)

    best = candidates[0] if candidates else None
    score = best["score"] if best else 0.0

    # Always check supplement table — it takes priority over RxNorm drug type classification
    supplement = lookup_supplement(cleaned) or lookup_supplement(input_text.lower().strip())

    if best and score >= 4.0:
        info = await get_drug_info(best["rxcui"])
        confidence = _rxnorm_score_to_confidence(score)

        if supplement:
            # Supplement table match: use RxNorm rxcui but override type and active_compounds
            return Medication(
                rxcui=info["rxcui"] if info else best["rxcui"],
                name=supplement["canonical_name"],
                input_text=input_text,
                dose=dose,
                frequency=frequency,
                type="supplement",
                confidence=confidence,
                active_compounds=supplement["active_compounds"],
            )

        if info:
            if info["is_prescription"]:
                drug_type = "prescription"
            elif is_known_otc(info["name"]):
                drug_type = "otc"
            else:
                drug_type = "otc"

            return Medication(
                rxcui=info["rxcui"],
                name=info["name"],
                brand_names=info["brand_names"],
                input_text=input_text,
                dose=dose,
                frequency=frequency,
                type=drug_type,
                confidence=confidence,
            )
        else:
            return Medication(
                rxcui=best["rxcui"],
                name=best["name"],
                input_text=input_text,
                dose=dose,
                frequency=frequency,
                type="otc",
                confidence=max(confidence - 0.15, 0.0),
            )

    # RxNorm score too low — use supplement fallback if available
    if supplement:
        return Medication(
            rxcui=None,
            name=supplement["canonical_name"],
            input_text=input_text,
            dose=dose,
            frequency=frequency,
            type="supplement",
            confidence=0.75,
            active_compounds=supplement["active_compounds"],
        )

    # No match anywhere — return with low confidence so the UI flags it
    return Medication(
        rxcui=None,
        name=cleaned or input_text,
        input_text=input_text,
        dose=dose,
        frequency=frequency,
        type="otc",
        confidence=0.30,
    )


def _split_drug_list(raw: str) -> list[str]:
    """Split a free-text drug list on newlines and commas, drop empties."""
    parts = re.split(r"[,\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


async def normalize_medications(raw_input: str) -> list[Medication]:
    drug_strings = _split_drug_list(raw_input)
    if not drug_strings:
        return []
    return list(await asyncio.gather(*[normalize_medication(s) for s in drug_strings]))
