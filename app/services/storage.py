from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import SourceItem
from app.schemas.source import SourceItem as SourceItemSchema


def save_source_items(
    db: Session,
    items: list[SourceItemSchema],
) -> dict[str, int | list[int]]:
    """
    Save source items to database with deduplication by URL hash.

    Returns:
        dict with 'saved' and 'duplicates' counts.
    """
    saved_count = 0
    duplicate_count = 0
    saved_item_ids: list[int] = []

    for item in items:
        url_hash = SourceItem.compute_url_hash(item.url)

        try:
            db_item = SourceItem(
                source_id=item.source_id,
                title=item.title,
                url=item.url,
                url_hash=url_hash,
                published_at=item.published_at,
                summary=item.summary,
            )
            db.add(db_item)
            db.commit()
            if db_item.id is not None:
                saved_item_ids.append(db_item.id)
            saved_count += 1
        except IntegrityError:
            db.rollback()
            duplicate_count += 1
            continue

    return {
        "saved": saved_count,
        "duplicates": duplicate_count,
        "saved_item_ids": saved_item_ids,
    }


def get_recent_items(
    db: Session,
    source_id: str | None = None,
    limit: int = 20,
) -> list[SourceItem]:
    """
    Retrieve recent items, optionally filtered by source.
    """
    query = db.query(SourceItem)

    if source_id:
        query = query.filter(SourceItem.source_id == source_id)

    return query.order_by(SourceItem.created_at.desc()).limit(limit).all()
