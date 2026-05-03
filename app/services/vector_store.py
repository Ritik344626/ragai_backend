"""Vector search helpers using pgvector in PostgreSQL."""

from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.services.embeddings import embed_text


def search_similar_chunks(
    db: Session,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """
    Search for chunks most similar to the query using pgvector.
    
    Args:
        db: Database session
        query: Query text to find similar chunks
        limit: Number of results to return
    
    Returns:
        List of similar chunks with similarity scores
    """
    # Embed the query
    query_embedding = embed_text(query)

    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    top_results = (
        db.query(Chunk, distance_expr)
        .filter(Chunk.embedding.isnot(None))
        .filter(Chunk.is_indexed.is_(True))
        .order_by(distance_expr)
        .limit(limit)
        .all()
    )

    retrieved = []
    for idx, (chunk, distance) in enumerate(top_results, start=1):
        similarity = max(0.0, 1.0 - float(distance))
        retrieved.append(
            {
                "rank": idx,
                "chunk_id": chunk.id,
                "text": chunk.text,
                "source_id": chunk.source_id,
                "url": chunk.url,
                "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
                "similarity_score": float(similarity),
            }
        )

    return retrieved
