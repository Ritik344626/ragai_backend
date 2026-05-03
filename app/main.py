from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.rag import router as rag_router
from app.api.routes.summarize import router as summarize_router
from app.api.routes.sources import router as sources_router
from app.core.config import settings
from app.db.base import Base
from app.db.connection import engine, ensure_database_exists
from app.db.schema import ensure_pgvector_extension, ensure_pgvector_schema

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(sources_router, prefix=settings.api_v1_prefix)
app.include_router(ingest_router, prefix=settings.api_v1_prefix)
app.include_router(rag_router, prefix=settings.api_v1_prefix)
app.include_router(summarize_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def bootstrap_database() -> None:
    ensure_database_exists()
    ensure_pgvector_extension(engine)
    Base.metadata.create_all(bind=engine)
    ensure_pgvector_schema(engine)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "message": "Welcome to RAG Trends API",
        "docs": "/docs",
    }
