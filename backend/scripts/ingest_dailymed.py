"""
Ingest top-200 US drug labels from DailyMed API → ChromaDB.

Fetches SPL XML for each drug, parses the 4 key sections by LOINC code,
chunks text, embeds via OpenAI, and upserts into the medsafe_labels collection.

Run from backend/:  python -m scripts.ingest_dailymed
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from pathlib import Path

import httpx
from lxml import etree

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DAILYMED_BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

# LOINC codes → human-readable section names
SECTION_LOINC = {
    "34073-7": "Drug Interactions",
    "34071-1": "Warnings",
    "34070-3": "Contraindications",
    "34084-4": "Adverse Reactions",
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
    "hydrocodone", "pregabalin", "insulin glargine", "methotrexate", "cyclosporine",
    "tacrolimus", "digoxin", "lithium", "phenytoin", "carbamazepine",
    "valproate", "theophylline", "aspirin", "acetaminophen", "ibuprofen",
    "naproxen", "cetirizine", "loratadine", "fexofenadine", "montelukast",
    "atenolol", "carvedilol", "bisoprolol", "verapamil", "diltiazem",
    "nifedipine", "spironolactone", "allopurinol", "colchicine", "clopidogrel",
    "rivaroxaban", "apixaban", "dabigatran", "enoxaparin", "heparin",
    "insulin aspart", "insulin lispro", "glipizide", "glimepiride", "pioglitazone",
    "sitagliptin", "empagliflozin", "dapagliflozin", "liraglutide", "semaglutide",
    "enalapril", "ramipril", "benazepril", "captopril", "amlodipine",
    "irbesartan", "valsartan", "candesartan", "telmisartan", "olmesartan",
    "hydralazine", "clonidine", "methyldopa", "doxazosin", "terazosin",
    "tamsulosin", "finasteride", "dutasteride", "sildenafil", "tadalafil",
    "levothyroxine", "methimazole", "propylthiouracil", "calcitonin", "alendronate",
    "risedronate", "zoledronic acid", "denosumab", "raloxifene", "teriparatide",
    "calcium carbonate", "vitamin D3", "ferrous sulfate", "folic acid", "cyanocobalamin",
    "ondansetron", "metoclopramide", "promethazine", "prochlorperazine", "droperidol",
    "loperamide", "bismuth subsalicylate", "docusate", "polyethylene glycol", "lactulose",
    "ranitidine", "famotidine", "esomeprazole", "lansoprazole", "rabeprazole",
    "hydroxychloroquine", "azathioprine", "leflunomide", "sulfasalazine", "etanercept",
    "adalimumab", "infliximab", "rituximab", "trastuzumab", "bevacizumab",
    "imatinib", "erlotinib", "sorafenib", "tamoxifen", "letrozole",
    "anastrozole", "exemestane", "leuprolide", "bicalutamide", "enzalutamide",
    "acyclovir", "valacyclovir", "oseltamivir", "ribavirin", "tenofovir",
    "emtricitabine", "lamivudine", "zidovudine", "efavirenz", "lopinavir",
    "ritonavir", "atazanavir", "raltegravir", "dolutegravir", "bictegravir",
    "fluconazole", "itraconazole", "voriconazole", "amphotericin B", "caspofungin",
    "vancomycin", "daptomycin", "linezolid", "meropenem", "piperacillin",
    "ceftriaxone", "cefazolin", "clindamycin", "metronidazole", "trimethoprim",
    "nitrofurantoin", "rifampin", "isoniazid", "ethambutol", "pyrazinamide",
    "codeine", "morphine", "fentanyl", "buprenorphine", "naloxone",
    "naltrexone", "methadone", "oxymorphone", "hydromorphone", "tapentadol",
    "cyclobenzaprine", "tizanidine", "baclofen", "methocarbamol", "carisoprodol",
    "diphenhydramine", "hydroxyzine", "meclizine", "scopolamine", "benztropine",
    "donepezil", "memantine", "rivastigmine", "galantamine", "levodopa",
    "carbidopa", "ropinirole", "pramipexole", "entacapone", "selegiline",
    "topiramate", "lamotrigine", "levetiracetam", "oxcarbazepine", "lacosamide",
    "sumatriptan", "rizatriptan", "zolmitriptan", "propranolol", "amitriptyline",
    "nortriptyline", "venlafaxine", "mirtazapine", "trazodone", "buspirone",
    "haloperidol", "risperidone", "olanzapine", "clozapine", "ziprasidone",
    "lithium", "valproic acid", "lamotrigine", "divalproex", "oxcarbazepine",
]
# Deduplicate while preserving order
_seen: set[str] = set()
TOP_200_DRUGS = [d for d in TOP_200_DRUGS if not (d in _seen or _seen.add(d))]  # type: ignore[func-returns-value]


def _extract_text_from_xml(element) -> str:
    """Recursively extract plain text from an SPL XML element."""
    parts: list[str] = []
    if element.text:
        parts.append(element.text.strip())
    for child in element:
        tag = etree.QName(child.tag).localname if child.tag else ""
        if tag in {"content", "paragraph", "item", "caption", "td", "th"}:
            parts.append(_extract_text_from_xml(child))
        elif tag == "br":
            parts.append("\n")
        else:
            parts.append(_extract_text_from_xml(child))
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(p for p in parts if p)


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def fetch_setid(client: httpx.AsyncClient, drug_name: str) -> str | None:
    try:
        resp = await client.get(
            f"{DAILYMED_BASE}/drugs.json",
            params={"drug_name": drug_name, "pagesize": 1},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data", [])
        if results:
            return results[0].get("setid")
    except Exception as exc:
        logger.debug("DailyMed search failed for %s: %s", drug_name, exc)
    return None


async def fetch_spl_xml(client: httpx.AsyncClient, setid: str) -> bytes | None:
    try:
        resp = await client.get(f"{DAILYMED_BASE}/spls/{setid}.xml", timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        logger.debug("SPL fetch failed for setid %s: %s", setid, exc)
    return None


def parse_sections(xml_bytes: bytes) -> dict[str, str]:
    """Return {section_name: text} for target LOINC-coded sections."""
    sections: dict[str, str] = {}
    try:
        root = etree.fromstring(xml_bytes)
        # SPL uses HL7 namespace
        ns = {"spl": "urn:hl7-org:v3"}

        for section in root.iter("{urn:hl7-org:v3}section"):
            code_elem = section.find("{urn:hl7-org:v3}code")
            if code_elem is None:
                continue
            loinc = code_elem.get("code", "")
            if loinc not in SECTION_LOINC:
                continue
            text_elem = section.find("{urn:hl7-org:v3}text")
            if text_elem is None:
                continue
            raw = _extract_text_from_xml(text_elem)
            clean = _clean(raw)
            if len(clean) > 50:
                sections[SECTION_LOINC[loinc]] = clean
    except etree.XMLSyntaxError as exc:
        logger.debug("XML parse error: %s", exc)
    return sections


async def process_drug(
    client: httpx.AsyncClient,
    drug_name: str,
    chunks_out: list,
) -> None:
    from tools.rxnorm import approximate_term
    from rag.ingest import LabelChunk, _chunk_text

    setid = await fetch_setid(client, drug_name)
    if not setid:
        logger.debug("No DailyMed result for: %s", drug_name)
        return

    # Resolve RXCUI
    candidates = await approximate_term(drug_name, max_entries=1)
    rxcui = candidates[0]["rxcui"] if candidates else ""

    xml_bytes = await fetch_spl_xml(client, setid)
    if not xml_bytes:
        return

    sections = parse_sections(xml_bytes)
    if not sections:
        logger.debug("No target sections found for %s (setid=%s)", drug_name, setid)
        return

    for section_name, text in sections.items():
        text_chunks = _chunk_text(text)
        for i, chunk in enumerate(text_chunks):
            chunks_out.append(LabelChunk(
                setid=setid,
                rxcui=rxcui,
                drug_name=drug_name,
                section_type=section_name,
                version_date="",
                text=chunk,
                chunk_index=i,
            ))

    logger.info("Processed %-30s  setid=%-40s  sections=%s", drug_name, setid, list(sections))


async def main() -> None:
    from app.config import get_settings
    from rag.ingest import add_label_chunks, build_and_save_bm25_index

    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is required for DailyMed ingest. Aborting.")
        sys.exit(1)

    all_chunks: list = []
    rate_limit_delay = 0.5  # 2 req/sec to DailyMed

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i, drug_name in enumerate(TOP_200_DRUGS):
            await process_drug(client, drug_name, all_chunks)
            if (i + 1) % 20 == 0:
                logger.info("Progress: %d/%d drugs processed, %d chunks accumulated",
                            i + 1, len(TOP_200_DRUGS), len(all_chunks))
            time.sleep(rate_limit_delay)

    if not all_chunks:
        logger.warning("No chunks collected — nothing to embed.")
        return

    logger.info("Embedding and loading %d chunks into ChromaDB...", len(all_chunks))
    # Process in batches to avoid memory spikes
    batch = 200
    for i in range(0, len(all_chunks), batch):
        await add_label_chunks(all_chunks[i : i + batch])
        logger.info("Loaded chunks %d–%d", i, min(i + batch, len(all_chunks)))

    logger.info("Building BM25 index...")
    build_and_save_bm25_index()
    logger.info("DailyMed ingest complete. %d chunks loaded.", len(all_chunks))


if __name__ == "__main__":
    asyncio.run(main())
