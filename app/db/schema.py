from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_pgvector_extension(engine: Engine) -> None:
    """Ensure pgvector extension exists before creating vector columns."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))


def ensure_pgvector_schema(engine: Engine) -> None:
    """Apply pgvector extension and keep chunks.embedding in vector(384) format."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        table_exists = connection.execute(
            text("SELECT to_regclass('public.chunks')")
        ).scalar_one_or_none()
        if table_exists is None:
            return

        col_info = connection.execute(
            text(
                """
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'chunks'
                  AND column_name = 'embedding'
                """
            )
        ).scalar_one_or_none()

        if col_info is None:
            connection.execute(
                text("ALTER TABLE chunks ADD COLUMN embedding vector(384);")
            )
        elif col_info != "vector":
            connection.execute(
                text(
                    "ALTER TABLE chunks RENAME COLUMN embedding TO embedding_array_backup;"
                )
            )
            connection.execute(
                text("ALTER TABLE chunks ADD COLUMN embedding vector(384);")
            )
            connection.execute(
                text(
                    """
                    UPDATE chunks
                    SET embedding = embedding_array_backup::text::vector
                    WHERE embedding_array_backup IS NOT NULL
                      AND array_length(embedding_array_backup, 1) = 384
                    """
                )
            )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
                ON chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
        )
