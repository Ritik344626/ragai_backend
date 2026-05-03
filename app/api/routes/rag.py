from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.services.rag import index_source_item, search_chunks

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/index/{source_item_id}")
def index_item(
    source_item_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Index a source item: chunk, embed, and store in PostgreSQL.
    """
    try:
        result = index_source_item(db, source_item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index item: {exc}",
        ) from exc

    return {
        "source_item_id": source_item_id,
        "chunks_created": result["chunks_created"],
        "chunks_skipped": result["chunks_skipped"],
    }


@router.get("/search")
def search_rag(
    query: str = Query(..., min_length=3),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict:
    """
    Semantic search over indexed chunks using stored embeddings.
    
    Returns top-k relevant chunks with source metadata and similarity scores.
    """
    try:
        results = search_chunks(db, query, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {exc}",
        ) from exc

    return {
        "query": query,
        "result_count": len(results),
        "results": results,
    }
