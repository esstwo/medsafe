"""
Ingest top-200 US drug labels from openFDA drug label API → ChromaDB.

openFDA returns FDA label text in clean JSON (same underlying data as DailyMed SPL,
but via a reliable API with no XML parsing required). Extracts four key sections per
drug, chunks them, embeds via OpenAI, and upserts into the medsafe_labels collection.

Run from backend/:  python -m scripts.ingest_dailymed
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OPENFDA_BASE = "https://api.fda.gov/drug/label.json"

# openFDA field name → human-readable section name
SECTIONS = {
    "drug_interactions": "Drug Interactions",
    "warnings_and_cautions": "Warnings",
    "warnings": "Warnings",
    "contraindications": "Contraindications",
    "adverse_reactions": "Adverse Reactions",
}

# Top 200 most-prescribed US drugs (generic names)
TOP_200_DRUGS = [
    "atorvastatin", "metformin", "lisinopril", "levothyroxine", "amlodipine",
    "metoprolol", "omeprazole", "albuterol", "losartan", "gabapentin",
    "warfarin", "clopidogrel", "sertraline", "fluoxetine", "bupropion",
    "duloxetine", "escitalopram", "alprazolam", "clonazepam", "lorazepam",
    "zolpidem", "quetiapine", "aripiprazole", "pantoprazole", "rosuvastatin",
    "simvastatin", "hydrochlorothiazide", "furosemide", "prednisone", "amoxicillin",
    "azithromycin", "doxycycline", "ciprofloxacin", "tramadol", "oxycodone",
    "hydrocodone", "pregabalin", "methotrexate", "cyclosporine", "tacrolimus",
    "digoxin", "lithium", "phenytoin", "carbamazepine", "valproate",
    "theophylline", "aspirin", "acetaminophen", "ibuprofen", "naproxen",
    "cetirizine", "loratadine", "fexofenadine", "montelukant", "atenolol",
    "carvedilol", "bisoprolol", "verapamil", "diltiazem", "nifedipine",
    "spironolactone", "allopurinol", "colchicine", "rivaroxaban", "apixaban",
    "dabigatran", "enoxaparin", "glipizide", "glimepiride", "pioglitazone",
    "sitagliptin", "empagliflozin", "dapagliflozin", "enalapril", "ramipril",
    "irbesartan", "valsartan", "candesartan", "olmesartan", "hydralazine",
    "clonidine", "tamsulosin", "finasteride", "sildenafil", "tadalafil",
    "methimazole", "alendronate", "risedronate", "ondansetron", "metoclopramide",
    "promethazine", "loperamide", "polyethylene glycol", "esomeprazole",
    "lansoprazole", "rabeprazole", "hydroxychloroquine", "azathioprine",
    "leflunomide", "sulfasalazine", "acyclovir", "valacyclovir", "oseltamivir",
    "tenofovir", "emtricitabine", "fluconazole", "itraconazole", "voriconazole",
    "vancomycin", "linezolid", "meropenem", "ceftriaxone", "clindamycin",
    "metronidazole", "trimethoprim", "nitrofurantoin", "rifampin", "isoniazid",
    "codeine", "morphine", "fentanyl", "buprenorphine", "naloxone",
    "naltrexone", "methadone", "cyclobenzaprine", "tizanidine", "baclofen",
    "diphenhydramine", "hydroxyzine", "meclizine", "donepezil", "memantine",
    "levodopa", "carbidopa", "ropinirole", "pramipexole", "topiramate",
    "lamotrigine", "levetiracetam", "oxcarbazepine", "lacosamide", "sumatriptan",
    "propranolol", "amitriptyline", "nortriptyline", "venlafaxine", "mirtazapine",
    "trazodone", "buspirone", "haloperidol", "risperidone", "olanzapine",
    "clozapine", "ziprasidone", "divalproex", "insulin glargine", "insulin aspart",
    "liraglutide", "semaglutide", "tamoxifen", "letrozole", "anastrozole",
    "imatinib", "rituximab", "adalimumab", "etanercept", "infliximab",
    "clopidogrel", "aspirin", "warfarin", "heparin", "acetaminophen",
]

# Deduplicate while preserving order
_seen: set[str] = set()
TOP_200_DRUGS = [d for d in TOP_200_DRUGS if not (d in _seen or _seen.add(d))]  # type: ignore[func-returns-value]


async def fetch_label(
    client: httpx.AsyncClient,
    drug_name: str,
    api_key: str | None,
) -> dict | None:
    params: dict = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "limit": 1,
    }
    if api_key:
        params["api_key"] = api_key
    try:
        resp = await client.get(OPENFDA_BASE, params=params, timeout=15)
        if resp.status_code == 404:
            # Try brand name search as fallback
            params["search"] = f'openfda.brand_name:"{drug_name}"'
            resp = await client.get(OPENFDA_BASE, params=params, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        return results[0] if results else None
    except Exception as exc:
        logger.debug("openFDA fetch failed for %s: %s", drug_name, exc)
        return None


def extract_sections(label: dict) -> dict[str, str]:
    """Return {section_name: text} for target sections."""
    sections: dict[str, str] = {}
    seen_names: set[str] = set()
    for field, section_name in SECTIONS.items():
        if section_name in seen_names:
            continue  # skip 'warnings' if 'warnings_and_cautions' already found
        values = label.get(field)
        if values and isinstance(values, list) and values[0]:
            text = " ".join(values).strip()
            if len(text) > 100:
                sections[section_name] = text
                seen_names.add(section_name)
    return sections


async def process_drug(
    client: httpx.AsyncClient,
    drug_name: str,
    api_key: str | None,
    chunks_out: list,
) -> None:
    from tools.rxnorm import approximate_term
    from rag.ingest import LabelChunk, _chunk_text

    label = await fetch_label(client, drug_name, api_key)
    if not label:
        logger.debug("No FDA label found: %s", drug_name)
        return

    openfda = label.get("openfda", {})
    rxcuis = openfda.get("rxcui", [])
    rxcui = rxcuis[0] if rxcuis else ""
    setid = (openfda.get("spl_set_id") or [""])[0]

    if not rxcui:
        candidates = await approximate_term(drug_name, max_entries=1)
        rxcui = candidates[0]["rxcui"] if candidates else ""

    sections = extract_sections(label)
    if not sections:
        logger.debug("No target sections for %s", drug_name)
        return

    for section_name, text in sections.items():
        for i, chunk in enumerate(_chunk_text(text)):
            chunks_out.append(LabelChunk(
                setid=setid,
                rxcui=rxcui,
                drug_name=drug_name,
                section_type=section_name,
                version_date="",
                text=chunk,
                chunk_index=i,
            ))

    logger.info("%-30s  rxcui=%-12s  sections=%s  chunks=%d",
                drug_name, rxcui, list(sections), sum(1 for _ in sections))


async def main() -> None:
    from app.config import get_settings
    from rag.ingest import add_label_chunks, build_and_save_bm25_index

    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is required. Aborting.")
        sys.exit(1)

    api_key = settings.openfda_api_key or None
    all_chunks: list = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i, drug_name in enumerate(TOP_200_DRUGS):
            await process_drug(client, drug_name, api_key, all_chunks)
            if (i + 1) % 25 == 0:
                logger.info("Progress: %d/%d drugs, %d chunks so far",
                            i + 1, len(TOP_200_DRUGS), len(all_chunks))
            time.sleep(0.25)  # ~4 req/sec; openFDA allows 240/min with key, 40/min without

    if not all_chunks:
        logger.warning("No chunks collected — check network or API key.")
        return

    logger.info("Embedding and loading %d chunks into ChromaDB...", len(all_chunks))
    batch = 200
    for i in range(0, len(all_chunks), batch):
        await add_label_chunks(all_chunks[i: i + batch])
        logger.info("Loaded chunks %d–%d", i, min(i + batch, len(all_chunks)))

    logger.info("Building BM25 index...")
    build_and_save_bm25_index()
    logger.info("Done. %d chunks loaded into ChromaDB.", len(all_chunks))


if __name__ == "__main__":
    asyncio.run(main())
