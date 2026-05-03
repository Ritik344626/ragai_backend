import hashlib
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SourceItem(Base, TimestampMixin):
    __tablename__ = "source_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    url_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_processed: Mapped[bool] = mapped_column(default=False, index=True)

    __table_args__ = (
        Index("idx_source_published", "source_id", "published_at"),
        Index("idx_processed_created", "is_processed", "created_at"),
    )

    @staticmethod
    def compute_url_hash(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def __repr__(self) -> str:
        return f"<SourceItem(id={self.id}, source={self.source_id}, title={self.title[:50]})>"


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_item_id: Mapped[int] = mapped_column(nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=True)
    embedding: Mapped[Vector | None] = mapped_column(Vector(384), nullable=True)
    is_indexed: Mapped[bool] = mapped_column(default=False, index=True)

    __table_args__ = (
        Index("idx_chunk_source_indexed", "source_id", "is_indexed"),
    )

    @staticmethod
    def compute_chunk_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, item_id={self.source_item_id}, idx={self.chunk_index})>"
