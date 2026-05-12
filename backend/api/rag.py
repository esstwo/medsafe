from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from models.retrieval import RetrievalResult
from rag.retriever import retrieve

router = APIRouter()


class RetrieveRequest(BaseModel):
    rxcui_a: str | None = None
    rxcui_b: str | None = None
    query: str | None = None  # auto-built from drug names if omitted
    top_k: int = 5


class RetrieveResponse(BaseModel):
    results: list[RetrievalResult]
    supabase_exact: dict | None = None   # exact Supabase hit if found


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_endpoint(req: RetrieveRequest) -> RetrieveResponse:
    query = req.query
    if not query:
        parts = [r for r in [req.rxcui_a, req.rxcui_b] if r]
        query = "drug interaction " + " ".join(parts)

    # Supabase exact lookup (fast path, no embeddings needed)
    supabase_exact: dict | None = None
    if req.rxcui_a and req.rxcui_b and get_settings().database_url:
        try:
            from db.client import get_pool
            from db.interactions import lookup_interaction
            pool = await get_pool()
            supabase_exact = await lookup_interaction(pool, req.rxcui_a, req.rxcui_b)
        except Exception:
            pass

    # ChromaDB + BM25 hybrid search (requires OpenAI key for dense; BM25-only otherwise)
    rag_results = await retrieve(
        query=query,
        rxcui_a=req.rxcui_a,
        rxcui_b=req.rxcui_b,
        top_k=req.top_k,
    )

    # If Supabase has an exact match and it's not already in RAG results, prepend it
    if supabase_exact and supabase_exact.get("description"):
        already_present = any(
            supabase_exact["description"][:50] in r.text for r in rag_results
        )
        if not already_present:
            rag_results.insert(0, RetrievalResult(
                text=supabase_exact["description"],
                source_type="drugbank_interaction",
                rxcui=supabase_exact["rxcui_a"],
                drug_name=supabase_exact.get("drug_a_name"),
                severity=supabase_exact.get("severity"),
                score=1.0,  # exact match gets highest score
                drugbank_id=supabase_exact.get("drugbank_id"),
            ))

    return RetrieveResponse(results=rag_results[:req.top_k], supabase_exact=supabase_exact)
