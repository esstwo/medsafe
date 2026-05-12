"""OpenFDA FAERS adverse event client."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse

import httpx

from app.config import get_settings
from models.briefing import FAERSResult
from models.medication import Medication

logger = logging.getLogger(__name__)

FAERS_BASE = "https://api.fda.gov/drug/event.json"
_SPARSE_THRESHOLD = 10


def _params(extra: dict) -> dict:
    p = {"limit": 1}
    p.update(extra)
    key = get_settings().openfda_api_key
    if key:
        p["api_key"] = key
    return p


def _search(drug_name: str, field: str = "openfda.generic_name", extra: str = "") -> str:
    # Use space-delimited AND — httpx encodes spaces as %20, openFDA accepts both
    q = f'patient.drug.{field}:"{drug_name}"'
    if extra:
        q += f" AND {extra}"
    return q


async def _fetch_total(client: httpx.AsyncClient, search: str) -> int:
    try:
        resp = await client.get(FAERS_BASE, params=_params({"search": search}), timeout=10)
        if resp.status_code == 404:
            return 0
        resp.raise_for_status()
        return resp.json().get("meta", {}).get("results", {}).get("total", 0)
    except Exception as exc:
        logger.debug("FAERS total fetch failed: %s", exc)
        return 0


async def _fetch_reactions(client: httpx.AsyncClient, search: str) -> list[str]:
    try:
        params = _params({
            "search": search,
            "count": "patient.reaction.reactionmeddrapt.exact",
            "limit": 10,
        })
        del params["limit"]  # count endpoint uses its own limit
        params["limit"] = 10
        resp = await client.get(FAERS_BASE, params=params, timeout=10)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [r["term"].title() for r in results]
    except Exception as exc:
        logger.debug("FAERS reactions fetch failed: %s", exc)
        return []


async def get_faers_data(drug_name: str, rxcui: str | None = None) -> FAERSResult:
    """Fetch FAERS adverse event data for a single drug name."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        generic_search = _search(drug_name, "openfda.generic_name")

        total, serious, reactions = await asyncio.gather(
            _fetch_total(client, generic_search),
            _fetch_total(client, _search(drug_name, "openfda.generic_name", "serious:1")),
            _fetch_reactions(client, generic_search),
        )

        # Brand-name fallback if generic returns nothing
        if total == 0:
            brand_search = _search(drug_name, "openfda.brand_name")
            total, serious, reactions = await asyncio.gather(
                _fetch_total(client, brand_search),
                _fetch_total(client, _search(drug_name, "openfda.brand_name", "serious:1")),
                _fetch_reactions(client, brand_search),
            )

    return FAERSResult(
        drug_name=drug_name,
        rxcui=rxcui,
        total_reports=total,
        serious_outcomes=serious,
        top_reactions=reactions,
        data_sparse=total < _SPARSE_THRESHOLD,
    )


async def get_faers_batch(medications: list[Medication]) -> list[FAERSResult]:
    """Fetch FAERS data for a list of medications, deduplicating by name."""
    seen: dict[str, FAERSResult] = {}
    tasks = []
    unique_meds: list[Medication] = []
    for med in medications:
        if med.name not in seen:
            seen[med.name] = None  # type: ignore[assignment]
            unique_meds.append(med)

    results = await asyncio.gather(*[get_faers_data(m.name, m.rxcui) for m in unique_meds])
    for med, result in zip(unique_meds, results):
        seen[med.name] = result

    return [seen[med.name] for med in medications]
