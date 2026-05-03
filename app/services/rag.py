from sqlalchemy.orm import Session

from app.db.models import Chunk, SourceItem
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.vector_store import search_similar_chunks


def index_source_item(db: Session, source_item_id: int) -> dict[str, int]:
    """
    Process a single source item: chunk it, embed chunks, store in PostgreSQL.
    
    Args:
        db: Database session
        source_item_id: ID of SourceItem to index
    
    Returns:
        dict with created and skipped chunk counts
    """
    source_item = db.query(SourceItem).filter(SourceItem.id == source_item_id).first()
    if not source_item:
        raise ValueError(f"SourceItem {source_item_id} not found")

    existing_indexed_chunks = (
        db.query(Chunk)
        .filter(Chunk.source_item_id == source_item_id)
        .filter(Chunk.is_indexed.is_(True))
        .count()
    )
    if source_item.is_processed and existing_indexed_chunks > 0:
        return {"chunks_created": 0, "chunks_skipped": existing_indexed_chunks}
    
    # Prepare text to chunk
    text_to_chunk = (
        f"{source_item.title}\n\n{source_item.summary or ''}\n\n{source_item.raw_content or ''}"
    )
    if not text_to_chunk.strip():
        return {"chunks_created": 0, "chunks_skipped": 0}
    
    # Chunk the text
    chunks = chunk_text(text_to_chunk)
    if not chunks:
        return {"chunks_created": 0, "chunks_skipped": 0}
    
    # Embed all chunks in batch
    embeddings = embed_texts(chunks)
    
    existing_hashes = {
        row[0]
        for row in db.query(Chunk.chunk_hash)
        .filter(Chunk.source_item_id == source_item_id)
        .all()
    }

    # Save chunks to PostgreSQL with embeddings
    created_count = 0
    skipped_count = 0
    for idx, (chunk_text_val, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_hash = Chunk.compute_chunk_hash(chunk_text_val)
        if chunk_hash in existing_hashes:
            skipped_count += 1
            continue
        
        db_chunk = Chunk(
            source_item_id=source_item_id,
            chunk_index=idx,
            text=chunk_text_val,
            chunk_hash=chunk_hash,
            source_id=source_item.source_id,
            published_at=source_item.published_at,
            url=source_item.url,
            embedding=embedding,
            is_indexed=True,
        )
        db.add(db_chunk)
        existing_hashes.add(chunk_hash)
        created_count += 1
    
    source_item.is_processed = (
        (created_count > 0) or (skipped_count > 0) or (existing_indexed_chunks > 0)
    )
    db.commit()
    
    return {"chunks_created": created_count, "chunks_skipped": skipped_count}


def search_chunks(db: Session, query: str, limit: int = 5) -> list[dict]:
    """
    Search for relevant chunks using cosine similarity over stored embeddings.
    
    Args:
        db: Database session
        query: Query text
        limit: Number of results to return
    
    Returns:
        List of relevant chunks with metadata and similarity scores
    """
    return search_similar_chunks(db, query, limit=limit)
