from __future__ import annotations

from celery import Task

from app.celery_app import celery_app
from app.core.config import settings
from app.db.base import Base
from app.db.connection import SessionLocal, engine, ensure_database_exists
from app.db.models import SourceItem
from app.db.schema import ensure_pgvector_extension, ensure_pgvector_schema
from app.services.content_extraction import extract_full_content
from app.services.rag import index_source_item
from app.services.sources.source_service import fetch_source_preview, list_sources
from app.services.storage import save_source_items

_DB_BOOTSTRAPPED = False


def _ensure_database_ready() -> None:
    global _DB_BOOTSTRAPPED
    if _DB_BOOTSTRAPPED:
        return
    ensure_database_exists()
    ensure_pgvector_extension(engine)
    Base.metadata.create_all(bind=engine)
    ensure_pgvector_schema(engine)
    _DB_BOOTSTRAPPED = True


def _auto_source_ids() -> list[str]:
    configured = [raw.strip() for raw in settings.celery_auto_sources_csv.split(",")]
    configured = [source for source in configured if source]
    if configured:
        return configured
    return [source.id for source in list_sources()]


def _enrich_item_content(item: SourceItem) -> bool:
    if item.raw_content and len(item.raw_content.strip()) >= 120:
        return False
    if not item.url:
        return False

    try:
        raw_content = extract_full_content(item.url)
    except Exception:
        return False

    if not raw_content:
        return False

    item.raw_content = raw_content
    if not item.summary:
        item.summary = raw_content[:400]
    return True


def _run_source_pipeline_impl(source_id: str, limit: int | None = None) -> dict:
    _ensure_database_ready()
    normalized_limit = max(1, min(limit or settings.ingestion_default_limit, 50))
    db = SessionLocal()

    try:
        items = fetch_source_preview(source_id=source_id, limit=normalized_limit)
        storage_result = save_source_items(db, items)

        enriched_count = 0
        indexed_count = 0
        created_chunks = 0

        for item_id in storage_result["saved_item_ids"]:
            source_item = db.query(SourceItem).filter(SourceItem.id == item_id).first()
            if source_item is None:
                continue

            if _enrich_item_content(source_item):
                enriched_count += 1
                db.commit()

            index_result = index_source_item(db, source_item.id)
            if index_result["chunks_created"] > 0 or index_result["chunks_skipped"] > 0:
                indexed_count += 1
                created_chunks += index_result["chunks_created"]

        return {
            "source_id": source_id,
            "fetched": len(items),
            "saved": storage_result["saved"],
            "duplicates": storage_result["duplicates"],
            "enriched": enriched_count,
            "indexed_items": indexed_count,
            "chunks_created": created_chunks,
        }
    finally:
        db.close()


def _process_unprocessed_items_impl(limit: int = 100) -> dict:
    _ensure_database_ready()
    db = SessionLocal()
    try:
        pending_items = (
            db.query(SourceItem)
            .filter(SourceItem.is_processed.is_(False))
            .order_by(SourceItem.created_at.asc())
            .limit(max(1, min(limit, 500)))
            .all()
        )

        processed = 0
        enriched = 0
        chunks_created = 0

        for source_item in pending_items:
            if _enrich_item_content(source_item):
                enriched += 1
                db.commit()

            result = index_source_item(db, source_item.id)
            if result["chunks_created"] > 0 or result["chunks_skipped"] > 0:
                processed += 1
                chunks_created += result["chunks_created"]

        return {
            "pending_items_scanned": len(pending_items),
            "items_processed": processed,
            "items_enriched": enriched,
            "chunks_created": chunks_created,
        }
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion_tasks.run_source_pipeline",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_source_pipeline(self: Task, source_id: str, limit: int | None = None) -> dict:
    return _run_source_pipeline_impl(source_id=source_id, limit=limit)


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion_tasks.run_all_sources_pipeline",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def run_all_sources_pipeline(self: Task, limit: int | None = None) -> dict:
    aggregated: list[dict] = []
    total_fetched = 0
    total_saved = 0
    total_duplicates = 0
    total_chunks = 0

    for source_id in _auto_source_ids():
        result = _run_source_pipeline_impl(source_id=source_id, limit=limit)
        aggregated.append(result)
        total_fetched += int(result.get("fetched", 0))
        total_saved += int(result.get("saved", 0))
        total_duplicates += int(result.get("duplicates", 0))
        total_chunks += int(result.get("chunks_created", 0))

    return {
        "sources": aggregated,
        "total_fetched": total_fetched,
        "total_saved": total_saved,
        "total_duplicates": total_duplicates,
        "total_chunks_created": total_chunks,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion_tasks.process_unprocessed_items",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def process_unprocessed_items(self: Task, limit: int = 100) -> dict:
    return _process_unprocessed_items_impl(limit=limit)
