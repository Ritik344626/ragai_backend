from celery.exceptions import CeleryError
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.connection import get_db
from app.services.sources.source_service import fetch_source_preview, list_sources
from app.services.storage import get_recent_items, save_source_items
from app.tasks.ingestion_tasks import (
    process_unprocessed_items,
    run_all_sources_pipeline,
    run_source_pipeline,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _assert_source_exists(source_id: str) -> None:
    valid_source_ids = {source.id for source in list_sources()}
    if source_id not in valid_source_ids:
        raise HTTPException(status_code=404, detail=f"Unsupported source_id: {source_id}")


def _enqueue_task(task_call, detail: str):
    try:
        return task_call()
    except CeleryError as exc:
        raise HTTPException(status_code=503, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=detail) from exc


@router.post("/fetch-and-save/{source_id}")
def ingest_and_save(
    source_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    """
    Fetch items from a source and save to database with dedup.
    """
    try:
        items = fetch_source_preview(source_id=source_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch source '{source_id}': {exc}",
        ) from exc

    result = save_source_items(db, items)

    return {
        "source_id": source_id,
        "fetched": len(items),
        "saved": result["saved"],
        "duplicates": result["duplicates"],
    }


@router.post("/auto/{source_id}")
def queue_auto_ingest(
    source_id: str,
    limit: int = Query(default=15, ge=1, le=50),
) -> dict:
    """
    Queue full ingestion pipeline in Celery:
    fetch -> save -> extract content -> chunk -> embed -> index.
    """
    _assert_source_exists(source_id)
    task = _enqueue_task(
        lambda: run_source_pipeline.delay(source_id=source_id, limit=limit),
        "Failed to queue source ingestion task. Check Redis/Celery connectivity.",
    )
    return {
        "status": "queued",
        "task_id": task.id,
        "source_id": source_id,
        "limit": limit,
    }


@router.post("/auto-all")
def queue_auto_ingest_all(
    limit: int = Query(default=15, ge=1, le=50),
) -> dict:
    """
    Queue full ingestion pipeline across all configured sources in Celery.
    """
    task = _enqueue_task(
        lambda: run_all_sources_pipeline.delay(limit=limit),
        "Failed to queue all-sources ingestion task. Check Redis/Celery connectivity.",
    )
    return {
        "status": "queued",
        "task_id": task.id,
        "scope": "all_sources",
        "limit": limit,
    }


@router.post("/auto-process-pending")
def queue_process_pending_items(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """
    Queue processing of already-saved but not-yet-indexed items.
    """
    task = _enqueue_task(
        lambda: process_unprocessed_items.delay(limit=limit),
        "Failed to queue pending-items task. Check Redis/Celery connectivity.",
    )
    return {
        "status": "queued",
        "task_id": task.id,
        "scope": "pending_items",
        "limit": limit,
    }


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str) -> dict:
    """
    Check Celery task status and result payload.
    """
    result = AsyncResult(task_id, app=celery_app)
    response: dict = {
        "task_id": task_id,
        "state": result.state,
    }

    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)

    return response


@router.get("/items")
def get_items(
    source_id: str | None = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """
    Retrieve recently saved items, optionally filtered by source.
    """
    items = get_recent_items(db, source_id=source_id, limit=limit)

    return {
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "source_id": item.source_id,
                "title": item.title,
                "url": item.url,
                "published_at": item.published_at,
                "created_at": item.created_at,
            }
            for item in items
        ],
    }
