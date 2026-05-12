# Week 2 — RAG Pipeline

## What We're Building and Why

Builds the data layer Week 3's interaction checker reads from:
- **Supabase (PostgreSQL)**: structured DrugBank interaction records for exact O(1) lookup by RXCUI pair
- **ChromaDB**: FDA drug label sections (DailyMed) + DrugBank descriptions, embedded with text-embedding-3-small, for RAG fallback when no exact match exists
- **Hybrid retriever**: dense (ChromaDB) + BM25 keyword + RRF fusion → optional cross-encoder rerank

SQLite replaced by Supabase from day one (plan already said SQLite→PostgreSQL prod).

**Deliverable:** `POST /api/rag/retrieve {rxcui_a, rxcui_b, query}` → top-5 ranked text chunks with source metadata.

## Implementation Tasks

- [x] `backend/pyproject.toml` — add 7 new dependencies
- [x] `.env.example` — add DATABASE_URL, DRUGBANK_XML_PATH
- [x] `backend/app/config.py` — add database_url, drugbank_xml_path fields
- [x] `backend/db/client.py` — asyncpg connection pool
- [x] `backend/db/interactions.py` — upsert + lookup queries
- [x] `backend/models/retrieval.py` — RetrievalResult Pydantic model
- [x] `backend/rag/ingest.py` — ChromaDB client, chunking, OpenAI embedding pipeline, BM25 index build
- [x] `backend/rag/retriever.py` — dense + BM25 + RRF hybrid search
- [x] `backend/rag/reranker.py` — optional cross-encoder (graceful ImportError)
- [x] `backend/scripts/ingest_drugbank.py` — DrugBank XML parse or stub seed → Supabase + ChromaDB
- [x] `backend/scripts/ingest_dailymed.py` — top-200 drug labels from DailyMed API → ChromaDB
- [x] `backend/scripts/ingest_nih_ods.py` — NIH ODS scrape to data/nih_ods/ (download only)
- [x] `backend/api/rag.py` — POST /api/rag/retrieve test endpoint
- [x] `backend/app/main.py` — update lifespan: DB pool + ChromaDB init

## Changes Made

### DB layer
- `backend/db/client.py`: asyncpg pool, get_pool() / close_pool() singletons
- `backend/db/interactions.py`: upsert_interaction(), lookup_interaction() (order-independent RXCUI lookup)

### Models
- `backend/models/retrieval.py`: RetrievalResult with text, source_type, rxcui, section_type, severity, score, setid, drugbank_id

### RAG ingest
- `backend/rag/ingest.py`: ChromaDB setup (medsafe_labels + medsafe_interactions collections), OpenAI batch embedding, 600-token chunking with 100-token overlap, BM25 index build + pickle persist

### Scripts
- `backend/scripts/ingest_drugbank.py`: Mode A (XML) or Mode B (25-pair stub seed) → Supabase upsert + ChromaDB embed
- `backend/scripts/ingest_dailymed.py`: top-200 drug list, DailyMed API fetch, SPL XML parse by LOINC section codes, ChromaDB load
- `backend/scripts/ingest_nih_ods.py`: NIH ODS scrape + save to data/nih_ods/ (not indexed)

### Retrieval
- `backend/rag/retriever.py`: dense ChromaDB query (rxcui-filtered) + BM25 (loaded from pickle) + RRF fusion
- `backend/rag/reranker.py`: optional cross-encoder, caught with ImportError

### API + app wiring
- `backend/api/rag.py`: POST /api/rag/retrieve
- `backend/app/main.py`: lifespan now initialises DB pool and ChromaDB
