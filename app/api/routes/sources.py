from fastapi import APIRouter, HTTPException, Query

from app.schemas.source import SourceInfo, SourcePreviewResponse
from app.services.sources.source_service import fetch_source_preview, list_sources

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceInfo])
def get_sources() -> list[SourceInfo]:
    return list_sources()


@router.get("/{source_id}/preview", response_model=SourcePreviewResponse)
def preview_source(
    source_id: str,
    limit: int = Query(default=5, ge=1, le=50),
) -> SourcePreviewResponse:
    try:
        items = fetch_source_preview(source_id=source_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch source preview for '{source_id}': {exc}",
        ) from exc

    return SourcePreviewResponse(
        source_id=source_id,
        fetched_count=len(items),
        items=items,
    )
