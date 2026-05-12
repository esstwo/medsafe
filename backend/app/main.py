import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from api.medications import router as medications_router
from api.rag import router as rag_router
from api.analysis import router as analysis_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Supabase connection pool
    if settings.database_url:
        from db.client import get_pool
        await get_pool()
        logger.info("Database pool ready")
    else:
        logger.warning("DATABASE_URL not set — Supabase features disabled")

    # ChromaDB + BM25 index
    from rag.ingest import init_chroma
    init_chroma()

    yield

    # Cleanup
    if settings.database_url:
        from db.client import close_pool
        await close_pool()


app = FastAPI(
    title="MedSafe API",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(medications_router, prefix="/api/medications")
app.include_router(rag_router, prefix="/api/rag")
app.include_router(analysis_router, prefix="/api/analysis")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
