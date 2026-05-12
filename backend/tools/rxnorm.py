from typing import TypedDict
import httpx

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"

# Term types that indicate a prescription drug in RxNorm
_PRESCRIPTION_TTY = {"SBD", "SCD", "BPCK", "GPCK", "SBDC", "SCDC"}

# Known OTC active ingredients (for classification when RxNorm tty is ambiguous)
_KNOWN_OTC = {
    "aspirin", "ibuprofen", "acetaminophen", "naproxen", "cetirizine",
    "loratadine", "diphenhydramine", "famotidine", "omeprazole", "ranitidine",
    "calcium carbonate", "loperamide", "dextromethorphan", "guaifenesin",
    "pseudoephedrine", "phenylephrine", "bismuth subsalicylate", "docusate",
    "sennosides", "polyethylene glycol",
}

# Supplement fallback table: common name variants → canonical data
# Used when RxNorm score is too low to trust
SUPPLEMENT_TABLE: dict[str, dict] = {
    "turmeric": {"active_compounds": ["curcumin"], "canonical_name": "turmeric"},
    "curcumin": {"active_compounds": ["curcumin"], "canonical_name": "turmeric"},
    "fish oil": {"active_compounds": ["omega-3 fatty acids", "EPA", "DHA"], "canonical_name": "fish oil"},
    "omega 3": {"active_compounds": ["omega-3 fatty acids", "EPA", "DHA"], "canonical_name": "fish oil"},
    "omega-3": {"active_compounds": ["omega-3 fatty acids", "EPA", "DHA"], "canonical_name": "fish oil"},
    "melatonin": {"active_compounds": ["melatonin"], "canonical_name": "melatonin"},
    "vitamin d": {"active_compounds": ["cholecalciferol"], "canonical_name": "vitamin D3"},
    "vitamin d3": {"active_compounds": ["cholecalciferol"], "canonical_name": "vitamin D3"},
    "vitamin d2": {"active_compounds": ["ergocalciferol"], "canonical_name": "vitamin D2"},
    "magnesium": {"active_compounds": ["magnesium"], "canonical_name": "magnesium"},
    "zinc": {"active_compounds": ["zinc"], "canonical_name": "zinc"},
    "coq10": {"active_compounds": ["coenzyme Q10", "ubiquinone"], "canonical_name": "CoQ10"},
    "coenzyme q10": {"active_compounds": ["coenzyme Q10", "ubiquinone"], "canonical_name": "CoQ10"},
    "ubiquinone": {"active_compounds": ["coenzyme Q10", "ubiquinone"], "canonical_name": "CoQ10"},
    "ginger": {"active_compounds": ["gingerols", "shogaols"], "canonical_name": "ginger"},
    "echinacea": {"active_compounds": ["echinacea"], "canonical_name": "echinacea"},
    "ashwagandha": {"active_compounds": ["withanolides"], "canonical_name": "ashwagandha"},
    "st. john's wort": {"active_compounds": ["hypericin", "hyperforin"], "canonical_name": "St. John's wort"},
    "st johns wort": {"active_compounds": ["hypericin", "hyperforin"], "canonical_name": "St. John's wort"},
    "valerian": {"active_compounds": ["valerenic acid"], "canonical_name": "valerian"},
    "garlic": {"active_compounds": ["allicin"], "canonical_name": "garlic"},
    "ginkgo": {"active_compounds": ["ginkgo flavonoids", "terpenoids"], "canonical_name": "ginkgo biloba"},
    "ginkgo biloba": {"active_compounds": ["ginkgo flavonoids", "terpenoids"], "canonical_name": "ginkgo biloba"},
    "glucosamine": {"active_compounds": ["glucosamine"], "canonical_name": "glucosamine"},
    "chondroitin": {"active_compounds": ["chondroitin sulfate"], "canonical_name": "chondroitin"},
    "probiotics": {"active_compounds": ["Lactobacillus", "Bifidobacterium"], "canonical_name": "probiotics"},
    "vitamin c": {"active_compounds": ["ascorbic acid"], "canonical_name": "vitamin C"},
    "ascorbic acid": {"active_compounds": ["ascorbic acid"], "canonical_name": "vitamin C"},
    "vitamin b12": {"active_compounds": ["cyanocobalamin", "methylcobalamin"], "canonical_name": "vitamin B12"},
    "vitamin b6": {"active_compounds": ["pyridoxine"], "canonical_name": "vitamin B6"},
    "folate": {"active_compounds": ["folic acid"], "canonical_name": "folate"},
    "folic acid": {"active_compounds": ["folic acid"], "canonical_name": "folic acid"},
    "iron": {"active_compounds": ["ferrous sulfate"], "canonical_name": "iron"},
    "calcium": {"active_compounds": ["calcium"], "canonical_name": "calcium"},
    "potassium": {"active_compounds": ["potassium"], "canonical_name": "potassium"},
    "selenium": {"active_compounds": ["selenium"], "canonical_name": "selenium"},
    "biotin": {"active_compounds": ["biotin"], "canonical_name": "biotin"},
    "milk thistle": {"active_compounds": ["silymarin"], "canonical_name": "milk thistle"},
    "saw palmetto": {"active_compounds": ["fatty acids", "phytosterols"], "canonical_name": "saw palmetto"},
    "black cohosh": {"active_compounds": ["triterpene glycosides"], "canonical_name": "black cohosh"},
    "evening primrose": {"active_compounds": ["gamma-linolenic acid"], "canonical_name": "evening primrose oil"},
    "evening primrose oil": {"active_compounds": ["gamma-linolenic acid"], "canonical_name": "evening primrose oil"},
    "kava": {"active_compounds": ["kavalactones"], "canonical_name": "kava"},
    "licorice": {"active_compounds": ["glycyrrhizin"], "canonical_name": "licorice root"},
    "licorice root": {"active_compounds": ["glycyrrhizin"], "canonical_name": "licorice root"},
    "elderberry": {"active_compounds": ["anthocyanins"], "canonical_name": "elderberry"},
    "berberine": {"active_compounds": ["berberine"], "canonical_name": "berberine"},
    "resveratrol": {"active_compounds": ["resveratrol"], "canonical_name": "resveratrol"},
    "quercetin": {"active_compounds": ["quercetin"], "canonical_name": "quercetin"},
    "alpha lipoic acid": {"active_compounds": ["alpha-lipoic acid"], "canonical_name": "alpha-lipoic acid"},
    "ala": {"active_compounds": ["alpha-lipoic acid"], "canonical_name": "alpha-lipoic acid"},
    "spirulina": {"active_compounds": ["phycocyanin", "spirulina"], "canonical_name": "spirulina"},
    "maca": {"active_compounds": ["maca root"], "canonical_name": "maca"},
    "rhodiola": {"active_compounds": ["rosavins", "salidroside"], "canonical_name": "rhodiola rosea"},
    "lion's mane": {"active_compounds": ["hericenones", "erinacines"], "canonical_name": "lion's mane mushroom"},
    "reishi": {"active_compounds": ["polysaccharides", "triterpenes"], "canonical_name": "reishi mushroom"},
}


class ApproximateCandidate(TypedDict):
    rxcui: str
    name: str
    score: int


class RxNormDrugInfo(TypedDict):
    rxcui: str
    name: str
    tty: str
    brand_names: list[str]
    is_prescription: bool


_client: httpx.AsyncClient | None = None


def get_rxnorm_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=RXNORM_BASE, timeout=10.0)
    return _client


async def approximate_term(term: str, max_entries: int = 10) -> list[ApproximateCandidate]:
    """Return deduplicated candidates sorted by score descending.

    RxNorm scores are floats in roughly the 0–20 range; exact matches typically
    score 10–15. Candidates from some sources omit the name field, so we group
    by rxcui and keep the best-scoring named entry.
    """
    client = get_rxnorm_client()
    try:
        resp = await client.get(
            "/approximateTerm.json",
            params={"term": term, "maxEntries": max_entries},
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("approximateGroup", {}).get("candidate", [])
    except (httpx.HTTPError, KeyError, ValueError):
        return []

    # Group by rxcui: take max score, use name from whichever entry has one
    by_rxcui: dict[str, ApproximateCandidate] = {}
    for c in raw:
        rxcui = c.get("rxcui", "")
        if not rxcui:
            continue
        score = float(c.get("score", 0))
        name = c.get("name", "")
        existing = by_rxcui.get(rxcui)
        if existing is None:
            by_rxcui[rxcui] = ApproximateCandidate(rxcui=rxcui, name=name, score=score)
        else:
            # Keep higher score; prefer entry that has a name
            if score > existing["score"] or (not existing["name"] and name):
                by_rxcui[rxcui] = ApproximateCandidate(
                    rxcui=rxcui,
                    name=name or existing["name"],
                    score=max(score, existing["score"]),
                )

    return sorted(by_rxcui.values(), key=lambda c: c["score"], reverse=True)


async def get_drug_info(rxcui: str) -> RxNormDrugInfo | None:
    client = get_rxnorm_client()
    try:
        props_resp = await client.get(f"/rxcui/{rxcui}/properties.json")
        props_resp.raise_for_status()
        props = props_resp.json().get("properties", {})
        if not props:
            return None

        name = props.get("name", "")
        tty = props.get("tty", "")

        brand_names: list[str] = []
        has_sbd = False

        related_resp = await client.get(f"/rxcui/{rxcui}/allrelated.json")
        if related_resp.status_code == 200:
            groups = related_resp.json().get("allRelatedGroup", {}).get("conceptGroup", [])
            for group in groups:
                group_tty = group.get("tty", "")
                if group_tty in {"SBD", "BPCK"}:
                    concepts = group.get("conceptProperties", [])
                    if concepts:
                        has_sbd = True
                    for concept in concepts[:5]:   # cap at 5 brand entries
                        bn = concept.get("name", "")
                        if bn:
                            brand_names.append(bn)

        # BN (Brand Name concept) is prescription if it has prescribable SBD forms
        is_prescription = tty in _PRESCRIPTION_TTY or (tty == "BN" and has_sbd)

        return RxNormDrugInfo(
            rxcui=rxcui,
            name=name,
            tty=tty,
            brand_names=list(dict.fromkeys(brand_names)),
            is_prescription=is_prescription,
        )
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def lookup_supplement(name: str) -> dict | None:
    """Return supplement table entry for a normalized name, or None."""
    key = name.lower().strip()
    if key in SUPPLEMENT_TABLE:
        return SUPPLEMENT_TABLE[key]
    # Try removing common suffixes/prefixes before giving up
    for entry_key in SUPPLEMENT_TABLE:
        if entry_key in key or key in entry_key:
            return SUPPLEMENT_TABLE[entry_key]
    return None


def is_known_otc(name: str) -> bool:
    return name.lower().strip() in _KNOWN_OTC
