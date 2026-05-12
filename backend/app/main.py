from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from api.medications import router as medications_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Placeholder for future DB init, RAG index warm-up, etc.
    yield


app = FastAPI(
    title="MedSafe API",
    version="0.1.0",
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


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
