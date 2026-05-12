"""Hybrid retrieval: dense (ChromaDB) + BM25 keyword + RRF fusion."""

from __future__ import annotations

import logging
from typing import Any

from models.retrieval import RetrievalResult
from rag.ingest import (
    embed_texts,
    get_interactions_collection,
    get_labels_collection,
    load_bm25_index,
)

logger = logging.getLogger(__name__)

_DENSE_CANDIDATES = 20
_BM25_CANDIDATES = 20
_RRF_K = 60


def _rrf(rankings: list[list[str]], k: int = _RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _chroma_to_results(
    chroma_result: dict[str, Any],
    source_type: str,
) -> list[tuple[str, RetrievalResult]]:
    """Convert a ChromaDB query result into (id, RetrievalResult) pairs."""
    pairs: list[tuple[str, RetrievalResult]] = []
    ids = chroma_result.get("ids", [[]])[0]
    docs = chroma_result.get("documents", [[]])[0]
    metas = chroma_result.get("metadatas", [[]])[0]

    for doc_id, text, meta in zip(ids, docs, metas):
        if source_type == "dailymed_label":
            result = RetrievalResult(
                text=text,
                source_type="dailymed_label",
                rxcui=meta.get("rxcui"),
                section_type=meta.get("section_type"),
                drug_name=meta.get("drug_name"),
                setid=meta.get("setid"),
            )
        else:
            result = RetrievalResult(
                text=text,
                source_type="drugbank_interaction",
                rxcui=meta.get("rxcui_a"),
                drug_name=meta.get("drug_a_name"),
                severity=meta.get("severity"),
                drugbank_id=meta.get("drugbank_id") or None,
            )
        pairs.append((doc_id, result))
    return pairs


async def retrieve(
    query: str,
    rxcui_a: str | None = None,
    rxcui_b: str | None = None,
    top_k: int = 5,
) -> list[RetrievalResult]:
    # -----------------------------------------------------------------------
    # Step 1: Dense search (ChromaDB), filtered by rxcui metadata
    # -----------------------------------------------------------------------
    query_embedding: list[float] | None = None
    try:
        query_embedding = (await embed_texts([query]))[0]
    except Exception as exc:
        logger.warning("Embedding failed (ChromaDB dense search skipped): %s", exc)

    labels_col = get_labels_collection()
    interactions_col = get_interactions_collection()

    rxcui_filter: dict | None = None
    if rxcui_a or rxcui_b:
        rxcuis = [r for r in [rxcui_a, rxcui_b] if r]
        rxcui_filter = {"rxcui": {"$in": rxcuis}} if len(rxcuis) == 1 else None

    label_where: dict | None = rxcui_filter

    # For interactions, filter by pair
    interaction_where: dict | None = None
    if rxcui_a and rxcui_b:
        interaction_where = {
            "$or": [
                {"$and": [{"rxcui_a": rxcui_a}, {"rxcui_b": rxcui_b}]},
                {"$and": [{"rxcui_a": rxcui_b}, {"rxcui_b": rxcui_a}]},
            ]
        }
    elif rxcui_a:
        interaction_where = {"$or": [{"rxcui_a": rxcui_a}, {"rxcui_b": rxcui_a}]}
    elif rxcui_b:
        interaction_where = {"$or": [{"rxcui_a": rxcui_b}, {"rxcui_b": rxcui_b}]}

    label_kwargs: dict = dict(
        query_embeddings=[query_embedding],
        n_results=_DENSE_CANDIDATES,
        include=["documents", "metadatas", "distances"],
    )
    if label_where:
        label_kwargs["where"] = label_where

    interaction_kwargs: dict = dict(
        query_embeddings=[query_embedding],
        n_results=min(_DENSE_CANDIDATES, max(1, interactions_col.count())),
        include=["documents", "metadatas", "distances"],
    )
    if interaction_where:
        interaction_kwargs["where"] = interaction_where

    dense_pairs: list[tuple[str, RetrievalResult]] = []

    if query_embedding is not None:
        label_kwargs["query_embeddings"] = [query_embedding]
        interaction_kwargs["query_embeddings"] = [query_embedding]

        try:
            if labels_col.count() > 0:
                label_res = labels_col.query(**label_kwargs)
                dense_pairs.extend(_chroma_to_results(label_res, "dailymed_label"))
        except Exception as exc:
            logger.warning("Label dense search failed: %s", exc)

        try:
            if interactions_col.count() > 0:
                int_res = interactions_col.query(**interaction_kwargs)
                dense_pairs.extend(_chroma_to_results(int_res, "drugbank_interaction"))
        except Exception as exc:
            logger.warning("Interaction dense search failed: %s", exc)

    dense_ranking = [doc_id for doc_id, _ in dense_pairs]
    all_results: dict[str, RetrievalResult] = {doc_id: res for doc_id, res in dense_pairs}

    # -----------------------------------------------------------------------
    # Step 2: BM25 keyword search
    # -----------------------------------------------------------------------
    bm25_ranking: list[str] = []
    bm25_index = load_bm25_index()
    if bm25_index and bm25_index.doc_ids:
        tokenized_query = query.lower().split()
        scores = bm25_index.index.get_scores(tokenized_query)

        # Filter to only docs matching the rxcui constraint (if any)
        allowed_ids: set[str] | None = None
        if rxcui_a or rxcui_b:
            rxcuis = {r for r in [rxcui_a, rxcui_b] if r}
            allowed_ids = {
                doc_id
                for doc_id in bm25_index.doc_ids
                if any(rxcui in doc_id for rxcui in rxcuis)
            }

        scored = sorted(
            (
                (score, doc_id)
                for score, doc_id in zip(scores, bm25_index.doc_ids)
                if score > 0 and (allowed_ids is None or doc_id in allowed_ids)
            ),
            reverse=True,
        )
        bm25_ranking = [doc_id for _, doc_id in scored[:_BM25_CANDIDATES]]

    # -----------------------------------------------------------------------
    # Step 3: Reciprocal Rank Fusion
    # -----------------------------------------------------------------------
    rrf_scores = _rrf([dense_ranking, bm25_ranking])

    fused_ids = sorted(rrf_scores, key=lambda d: rrf_scores[d], reverse=True)

    # Build final result list; fall back to dense_pairs for docs not in all_results
    fused_results: list[RetrievalResult] = []
    for doc_id in fused_ids:
        if doc_id in all_results:
            res = all_results[doc_id].model_copy()
            res.score = rrf_scores[doc_id]
            fused_results.append(res)

    # -----------------------------------------------------------------------
    # Step 4: Optional cross-encoder reranking
    # -----------------------------------------------------------------------
    try:
        from rag.reranker import rerank  # noqa: PLC0415
        fused_results = rerank(query, fused_results, top_k=top_k)
    except ImportError:
        fused_results = fused_results[:top_k]

    return fused_results
