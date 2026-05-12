"""ChromaDB setup, OpenAI embedding, chunking, and BM25 index management."""

from __future__ import annotations

import logging
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from openai import AsyncOpenAI
from rank_bm25 import BM25Okapi

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ChromaDB client (module-level singleton)
# ---------------------------------------------------------------------------

_chroma: chromadb.ClientAPI | None = None


def get_chroma() -> chromadb.ClientAPI:
    global _chroma
    if _chroma is None:
        settings = get_settings()
        path = Path(settings.chroma_persist_path)
        path.mkdir(parents=True, exist_ok=True)
        _chroma = chromadb.PersistentClient(path=str(path))
    return _chroma


def get_labels_collection() -> chromadb.Collection:
    return get_chroma().get_or_create_collection(
        name="medsafe_labels",
        metadata={"hnsw:space": "cosine"},
    )


def get_interactions_collection() -> chromadb.Collection:
    return get_chroma().get_or_create_collection(
        name="medsafe_interactions",
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# OpenAI embeddings
# ---------------------------------------------------------------------------

_openai: AsyncOpenAI | None = None

EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH = 512  # stay well under the 2048/request limit


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _openai


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings, batched to avoid API limits."""
    client = _get_openai()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        response = await client.embeddings.create(model=EMBED_MODEL, input=batch)
        embeddings.extend([item.embedding for item in response.data])
    return embeddings


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

CHUNK_TOKENS = 600
OVERLAP_TOKENS = 100
# Rough chars-per-token for English medical text; good enough for splitting
CHARS_PER_TOKEN = 4


def _chunk_text(text: str, chunk_tokens: int = CHUNK_TOKENS, overlap_tokens: int = OVERLAP_TOKENS) -> list[str]:
    """Split text into overlapping chunks on sentence boundaries."""
    chunk_chars = chunk_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    # Split on sentence-ending punctuation to avoid cutting mid-sentence
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > chunk_chars and current:
            chunks.append(current.strip())
            # Start next chunk with overlap from end of current chunk
            overlap_start = max(0, len(current) - overlap_chars)
            current = current[overlap_start:] + " " + sentence
        else:
            current = (current + " " + sentence).strip()

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:chunk_chars]]


# ---------------------------------------------------------------------------
# Dataclasses for typed ingest payloads
# ---------------------------------------------------------------------------

@dataclass
class LabelChunk:
    setid: str
    rxcui: str
    drug_name: str
    section_type: str
    version_date: str
    text: str
    chunk_index: int


@dataclass
class InteractionChunk:
    rxcui_a: str
    rxcui_b: str
    drug_a_name: str
    drug_b_name: str
    severity: str
    description: str
    drugbank_id: str | None = None


# ---------------------------------------------------------------------------
# Ingest helpers
# ---------------------------------------------------------------------------

async def add_label_chunks(chunks: list[LabelChunk]) -> None:
    if not chunks:
        return
    collection = get_labels_collection()

    # Deduplicate by ID within this batch (can happen when two drug names map
    # to the same FDA label, e.g. tenofovir + emtricitabine → Truvada)
    seen: set[str] = set()
    deduped: list[LabelChunk] = []
    for c in chunks:
        chunk_id = f"{c.setid}_{c.section_type.replace(' ', '_')}_{c.chunk_index}"
        if chunk_id not in seen:
            seen.add(chunk_id)
            deduped.append(c)
    chunks = deduped

    ids = [f"{c.setid}_{c.section_type.replace(' ', '_')}_{c.chunk_index}" for c in chunks]
    texts = [c.text for c in chunks]
    metadatas: list[dict[str, Any]] = [
        {
            "rxcui": c.rxcui,
            "section_type": c.section_type,
            "drug_name": c.drug_name,
            "setid": c.setid,
            "version_date": c.version_date,
        }
        for c in chunks
    ]
    embeddings = await embed_texts(texts)
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    logger.info("Upserted %d label chunks", len(chunks))


async def add_interaction_chunks(interactions: list[InteractionChunk]) -> None:
    if not interactions:
        return
    collection = get_interactions_collection()

    # Deduplicate by canonical pair ID before upserting
    seen: set[str] = set()
    deduped: list[InteractionChunk] = []
    for i in interactions:
        pair_id = f"drugbank_{min(i.rxcui_a, i.rxcui_b)}_{max(i.rxcui_a, i.rxcui_b)}"
        if pair_id not in seen:
            seen.add(pair_id)
            deduped.append(i)
    interactions = deduped

    ids = [
        f"drugbank_{min(i.rxcui_a, i.rxcui_b)}_{max(i.rxcui_a, i.rxcui_b)}"
        for i in interactions
    ]
    texts = [i.description for i in interactions]
    metadatas: list[dict[str, Any]] = [
        {
            "rxcui_a": i.rxcui_a,
            "rxcui_b": i.rxcui_b,
            "drug_a_name": i.drug_a_name,
            "drug_b_name": i.drug_b_name,
            "severity": i.severity,
            "drugbank_id": i.drugbank_id or "",
        }
        for i in interactions
    ]
    embeddings = await embed_texts(texts)
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    logger.info("Upserted %d interaction chunks", len(interactions))


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------

@dataclass
class BM25Index:
    index: BM25Okapi
    doc_ids: list[str]
    corpus: list[list[str]]


_bm25: BM25Index | None = None


def _bm25_path() -> Path:
    return Path(get_settings().chroma_persist_path).parent / "bm25_index.pkl"


def load_bm25_index() -> BM25Index | None:
    global _bm25
    if _bm25 is not None:
        return _bm25
    path = _bm25_path()
    if path.exists():
        with path.open("rb") as f:
            _bm25 = pickle.load(f)
        logger.info("Loaded BM25 index (%d docs)", len(_bm25.doc_ids))
    return _bm25


def build_and_save_bm25_index() -> None:
    """Rebuild BM25 index from all ChromaDB documents and persist to disk."""
    labels = get_labels_collection()
    interactions = get_interactions_collection()

    all_ids: list[str] = []
    all_texts: list[str] = []

    result = labels.get(include=["documents"])
    if result["ids"]:
        all_ids.extend(result["ids"])
        all_texts.extend(result["documents"] or [])

    result = interactions.get(include=["documents"])
    if result["ids"]:
        all_ids.extend(result["ids"])
        all_texts.extend(result["documents"] or [])

    if not all_texts:
        logger.warning("No documents found; BM25 index not built")
        return

    tokenized = [doc.lower().split() for doc in all_texts]
    index = BM25Okapi(tokenized)

    bm25_obj = BM25Index(index=index, doc_ids=all_ids, corpus=tokenized)
    path = _bm25_path()
    with path.open("wb") as f:
        pickle.dump(bm25_obj, f)

    global _bm25
    _bm25 = bm25_obj
    logger.info("Built and saved BM25 index (%d docs) → %s", len(all_ids), path)


def init_chroma() -> None:
    """Called at FastAPI startup: ensure ChromaDB is accessible and BM25 index is loaded."""
    get_labels_collection()
    get_interactions_collection()
    load_bm25_index()
    logger.info("ChromaDB initialised")
