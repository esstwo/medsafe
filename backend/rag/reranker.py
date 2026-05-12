"""Optional cross-encoder reranker. Only usable if sentence-transformers is installed."""

from __future__ import annotations

# This module is intentionally imported inside a try/except in retriever.py.
# If sentence-transformers is not installed, the ImportError propagates and
# the retriever falls back to RRF top-k results.

from sentence_transformers import CrossEncoder  # noqa: F401 — triggers ImportError if missing

from models.retrieval import RetrievalResult

_model: CrossEncoder | None = None
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(_MODEL_NAME)
    return _model


def rerank(query: str, candidates: list[RetrievalResult], top_k: int = 5) -> list[RetrievalResult]:
    if not candidates:
        return candidates
    model = _get_model()
    pairs = [(query, c.text) for c in candidates]
    scores: list[float] = model.predict(pairs).tolist()
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    results = []
    for score, result in ranked[:top_k]:
        res = result.model_copy()
        res.score = float(score)
        results.append(res)
    return results
