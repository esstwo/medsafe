"""
Ingest DrugBank interaction data → Supabase + ChromaDB.

Mode A: DRUGBANK_XML_PATH points to a valid drugbank XML file → parse and load all interactions.
Mode B: No XML found → seed with 25 hardcoded benchmark interactions.

Run from backend/:  python -m scripts.ingest_drugbank
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benchmark / stub seed — covers all 8 plan.md scenarios + common high-risk pairs
# ---------------------------------------------------------------------------

SEED_INTERACTIONS = [
    # (rxcui_a, name_a, rxcui_b, name_b, severity, description, drugbank_id)
    ("11289", "warfarin", "1191", "aspirin", "major",
     "Concurrent use of warfarin and aspirin significantly increases the risk of major bleeding events, "
     "including gastrointestinal and intracranial hemorrhage. Aspirin inhibits platelet aggregation and "
     "can displace warfarin from plasma protein binding sites, raising free warfarin concentrations. "
     "Monitor INR closely; avoid combination unless benefit clearly outweighs risk.", "DB-stub-001"),
    ("41493", "fluoxetine", "8124", "phenelzine", "major",
     "Combining SSRIs such as fluoxetine with MAOIs such as phenelzine can precipitate serotonin syndrome, "
     "a potentially life-threatening condition characterised by hyperthermia, agitation, myoclonus, and "
     "autonomic instability. At least 14 days should elapse after stopping an MAOI before starting an SSRI, "
     "and at least 5 weeks after stopping fluoxetine before starting an MAOI.", "DB-stub-002"),
    ("83367", "atorvastatin", "1114883", "turmeric", "moderate",
     "Curcumin, the active compound in turmeric, may inhibit CYP3A4 and P-glycoprotein, potentially "
     "increasing atorvastatin plasma concentrations and the risk of myopathy or rhabdomyolysis. "
     "Evidence is primarily from in vitro and animal studies; clinical significance is uncertain. "
     "Use with caution; monitor for muscle pain or weakness.", "DB-stub-003"),
    ("1191", "aspirin", "1114883", "turmeric", "moderate",
     "Both aspirin and curcumin (turmeric) inhibit platelet aggregation through different mechanisms. "
     "Concurrent use may have additive antiplatelet effects, increasing bleeding risk. "
     "Caution is advised particularly in patients with bleeding disorders or those on anticoagulants.", "DB-stub-004"),
    ("1191", "aspirin", "809242", "fish oil", "moderate",
     "Fish oil (omega-3 fatty acids) and aspirin both inhibit platelet aggregation. Concomitant use "
     "may have additive antiplatelet effects. At high fish oil doses (>3 g/day), bleeding risk may "
     "increase. Monitor patients on anticoagulants who use both agents.", "DB-stub-005"),
    ("40790", "omeprazole", "6809", "metformin", "minor",
     "Omeprazole may slightly increase metformin plasma concentrations by inhibiting renal tubular "
     "secretion via OCT transporters. The clinical significance is generally low; however, patients "
     "with renal impairment may warrant closer glucose monitoring.", "DB-stub-006"),
    ("29046", "lisinopril", "1114883", "ashwagandha", "unknown",
     "Limited data exist on the interaction between lisinopril and ashwagandha (Withania somnifera). "
     "Ashwagandha may have mild antihypertensive and thyroid-modulating effects. Theoretical additive "
     "blood pressure lowering is possible. Evidence is insufficient to characterise this interaction; "
     "monitor blood pressure if used together.", "DB-stub-007"),
    ("11289", "warfarin", "1009302", "st. john's wort", "major",
     "St. John's Wort is a potent inducer of CYP2C9 and P-glycoprotein, significantly reducing "
     "warfarin plasma concentrations and anticoagulant effect. INR can drop substantially, increasing "
     "thrombosis risk. This combination should generally be avoided.", "DB-stub-008"),
    ("41493", "fluoxetine", "5521", "ibuprofen", "moderate",
     "SSRIs reduce platelet serotonin uptake, impairing platelet aggregation. NSAIDs such as ibuprofen "
     "also impair platelet function and damage the gastric mucosa. Combined use substantially increases "
     "the risk of gastrointestinal bleeding.", "DB-stub-009"),
    ("83367", "atorvastatin", "4495", "clarithromycin", "major",
     "Clarithromycin is a potent CYP3A4 inhibitor. Co-administration with atorvastatin markedly "
     "increases atorvastatin plasma concentrations (up to 10-fold), greatly elevating the risk of "
     "myopathy and rhabdomyolysis. Avoid this combination; use an alternative antibiotic.", "DB-stub-010"),
    ("3521", "digoxin", "2393", "amiodarone", "major",
     "Amiodarone inhibits renal and biliary elimination of digoxin, increasing digoxin plasma "
     "concentrations by 50–100%. Digoxin toxicity (bradycardia, heart block, nausea, visual changes) "
     "may result. Reduce digoxin dose by 30–50% when starting amiodarone; monitor levels closely.", "DB-stub-011"),
    ("6448", "lithium", "5521", "ibuprofen", "major",
     "NSAIDs reduce renal prostaglandin synthesis, decreasing renal blood flow and lithium clearance. "
     "Lithium plasma concentrations can rise 25–60%, precipitating lithium toxicity (tremor, ataxia, "
     "confusion, renal damage). Avoid NSAIDs in lithium-treated patients; use acetaminophen instead.", "DB-stub-012"),
    ("8278", "phenytoin", "7454", "omeprazole", "moderate",
     "Omeprazole inhibits CYP2C19, the primary enzyme responsible for phenytoin metabolism. "
     "Co-administration may increase phenytoin plasma concentrations, increasing the risk of "
     "phenytoin toxicity (nystagmus, ataxia, confusion). Monitor phenytoin levels.", "DB-stub-013"),
    ("10600", "theophylline", "2551", "ciprofloxacin", "major",
     "Ciprofloxacin inhibits CYP1A2, the principal enzyme metabolising theophylline. "
     "Theophylline concentrations may increase 30–90%, leading to toxicity (nausea, seizures, "
     "arrhythmias). Reduce theophylline dose and monitor serum levels when co-prescribing.", "DB-stub-014"),
    ("72625", "methotrexate", "1191", "aspirin", "major",
     "Aspirin and other salicylates reduce renal tubular secretion of methotrexate and displace it "
     "from plasma protein binding sites, substantially increasing methotrexate concentrations and "
     "toxicity risk (myelosuppression, mucositis, nephrotoxicity). Avoid concurrent use.", "DB-stub-015"),
    ("321076", "clopidogrel", "1191", "aspirin", "moderate",
     "Dual antiplatelet therapy with clopidogrel and aspirin is used therapeutically after ACS or "
     "stent placement but significantly increases bleeding risk compared with either agent alone. "
     "Use only when the clinical benefit (e.g., stent thrombosis prevention) outweighs bleeding risk.", "DB-stub-016"),
    ("29046", "lisinopril", "7792", "potassium", "moderate",
     "ACE inhibitors such as lisinopril reduce aldosterone, impairing renal potassium excretion. "
     "Potassium supplementation or potassium-sparing diuretics can cause hyperkalaemia (weakness, "
     "arrhythmias, cardiac arrest). Monitor serum potassium regularly.", "DB-stub-017"),
    ("6809", "metformin", "16", "alcohol", "moderate",
     "Heavy alcohol consumption combined with metformin increases the risk of lactic acidosis, a rare "
     "but serious complication. Alcohol also causes hypoglycaemia and impairs hepatic glucose output. "
     "Patients should limit alcohol intake and avoid binge drinking.", "DB-stub-018"),
    ("41493", "fluoxetine", "40790", "omeprazole", "minor",
     "Both fluoxetine and omeprazole are metabolised by CYP2C19. Fluoxetine can inhibit CYP2C19, "
     "potentially increasing omeprazole exposure. The interaction is generally not clinically "
     "significant at standard doses but may warrant monitoring in poor CYP2C19 metabolisers.", "DB-stub-019"),
    ("83367", "atorvastatin", "1114883", "grapefruit", "moderate",
     "Grapefruit and grapefruit juice contain furanocoumarins that irreversibly inhibit intestinal "
     "CYP3A4, increasing atorvastatin AUC up to 2.5-fold. This raises myopathy risk. Patients should "
     "avoid consuming large quantities of grapefruit while taking atorvastatin.", "DB-stub-020"),
    ("36567", "carbamazepine", "41493", "fluoxetine", "moderate",
     "Fluoxetine inhibits CYP3A4 and CYP2D6, increasing carbamazepine plasma concentrations and "
     "the risk of carbamazepine toxicity (diplopia, dizziness, ataxia). Carbamazepine also induces "
     "CYP enzymes, potentially reducing fluoxetine efficacy. Monitor carbamazepine levels.", "DB-stub-021"),
    ("11289", "warfarin", "6809", "metformin", "minor",
     "Limited evidence suggests metformin may have a modest anticoagulant effect that could "
     "potentiate warfarin. The interaction is generally not clinically significant but INR should "
     "be monitored when starting or stopping metformin in patients on warfarin.", "DB-stub-022"),
    ("3498", "cyclosporine", "83367", "atorvastatin", "major",
     "Cyclosporine markedly increases atorvastatin plasma concentrations (up to 8-fold) by inhibiting "
     "OATP1B1/1B3 transporters and CYP3A4. This greatly elevates myopathy and rhabdomyolysis risk. "
     "Use the lowest effective atorvastatin dose (max 10 mg/day) or consider an alternative statin.", "DB-stub-023"),
    ("40254", "valproate", "8278", "phenytoin", "moderate",
     "Valproate displaces phenytoin from protein binding sites and inhibits its metabolism, initially "
     "increasing free phenytoin levels. With chronic use, valproate may also induce phenytoin "
     "metabolism. Monitor free phenytoin levels and adjust doses as needed.", "DB-stub-024"),
    ("321988", "escitalopram", "8124", "phenelzine", "major",
     "Like other SSRIs, escitalopram combined with MAOIs such as phenelzine carries a high risk of "
     "serotonin syndrome. Allow at least 14 days after stopping an MAOI before starting escitalopram, "
     "and 14 days after stopping escitalopram before starting an MAOI.", "DB-stub-025"),
]


async def seed_stub(pool, chroma_loaded: bool) -> None:
    from db.interactions import upsert_interaction
    from rag.ingest import InteractionChunk, add_interaction_chunks

    logger.info("Seeding %d benchmark interactions into Supabase...", len(SEED_INTERACTIONS))
    chunks: list[InteractionChunk] = []
    for row in SEED_INTERACTIONS:
        rxcui_a, name_a, rxcui_b, name_b, severity, description, drugbank_id = row
        await upsert_interaction(pool, {
            "rxcui_a": rxcui_a, "rxcui_b": rxcui_b,
            "drug_a_name": name_a, "drug_b_name": name_b,
            "severity": severity, "description": description,
            "drugbank_id": drugbank_id, "source": "stub",
        })
        chunks.append(InteractionChunk(
            rxcui_a=rxcui_a, rxcui_b=rxcui_b,
            drug_a_name=name_a, drug_b_name=name_b,
            severity=severity, description=description, drugbank_id=drugbank_id,
        ))

    if chroma_loaded:
        logger.info("Embedding and loading into ChromaDB...")
        await add_interaction_chunks(chunks)
    logger.info("Stub seed complete.")


async def parse_drugbank_xml(xml_path: Path, pool, chroma_loaded: bool) -> None:
    """Parse DrugBank XML (streaming) and load interactions."""
    from lxml import etree
    from tools.rxnorm import approximate_term
    from db.interactions import upsert_interaction
    from rag.ingest import InteractionChunk, add_interaction_chunks

    NS = "http://www.drugbank.ca"
    logger.info("Parsing DrugBank XML: %s", xml_path)

    count = 0
    chunks: list[InteractionChunk] = []
    batch_size = 50

    context = etree.iterparse(str(xml_path), events=("end",), tag=f"{{{NS}}}drug")
    for _, drug_elem in context:
        drug_name_elem = drug_elem.find(f"{{{NS}}}name")
        drug_name = drug_name_elem.text if drug_name_elem is not None else ""
        drugbank_id_elem = drug_elem.find(f"{{{NS}}}drugbank-id[@primary='true']")
        drugbank_id = drugbank_id_elem.text if drugbank_id_elem is not None else ""

        interactions_elem = drug_elem.find(f"{{{NS}}}drug-interactions")
        if interactions_elem is None:
            drug_elem.clear()
            continue

        for interaction in interactions_elem.findall(f"{{{NS}}}drug-interaction"):
            partner_name_elem = interaction.find(f"{{{NS}}}name")
            desc_elem = interaction.find(f"{{{NS}}}description")
            partner_name = partner_name_elem.text if partner_name_elem is not None else ""
            description = desc_elem.text if desc_elem is not None else ""

            if not description:
                continue

            # Resolve RXCUIs
            drug_candidates = await approximate_term(drug_name, max_entries=1)
            partner_candidates = await approximate_term(partner_name, max_entries=1)

            rxcui_a = drug_candidates[0]["rxcui"] if drug_candidates else ""
            rxcui_b = partner_candidates[0]["rxcui"] if partner_candidates else ""

            if not rxcui_a or not rxcui_b:
                continue

            record = {
                "rxcui_a": rxcui_a, "rxcui_b": rxcui_b,
                "drug_a_name": drug_name, "drug_b_name": partner_name,
                "severity": "unknown", "description": description,
                "drugbank_id": drugbank_id, "source": "drugbank",
            }
            await upsert_interaction(pool, record)
            chunks.append(InteractionChunk(
                rxcui_a=rxcui_a, rxcui_b=rxcui_b,
                drug_a_name=drug_name, drug_b_name=partner_name,
                severity="unknown", description=description, drugbank_id=drugbank_id,
            ))
            count += 1

            if chroma_loaded and len(chunks) >= batch_size:
                await add_interaction_chunks(chunks)
                chunks.clear()

        drug_elem.clear()

    if chroma_loaded and chunks:
        await add_interaction_chunks(chunks)

    logger.info("Loaded %d DrugBank interactions.", count)


async def main() -> None:
    from app.config import get_settings
    from db.client import get_pool, close_pool
    from rag.ingest import get_interactions_collection, build_and_save_bm25_index

    settings = get_settings()
    pool = await get_pool()

    chroma_loaded = bool(settings.openai_api_key)
    if not chroma_loaded:
        logger.warning("OPENAI_API_KEY not set — skipping ChromaDB embedding. Supabase only.")

    xml_path = Path(settings.drugbank_xml_path) if settings.drugbank_xml_path else None
    if xml_path and xml_path.exists():
        await parse_drugbank_xml(xml_path, pool, chroma_loaded)
    else:
        if xml_path:
            logger.warning("DrugBank XML not found at %s — using stub seed.", xml_path)
        else:
            logger.info("DRUGBANK_XML_PATH not set — using stub seed.")
        await seed_stub(pool, chroma_loaded)

    if chroma_loaded:
        logger.info("Building BM25 index...")
        build_and_save_bm25_index()

    await close_pool()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
