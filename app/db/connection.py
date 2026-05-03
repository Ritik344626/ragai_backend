import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _build_database_url(database_name: str) -> str:
    return (
        f"postgresql+psycopg2://"
        f"{settings.db_user}:{settings.db_password}@"
        f"{settings.db_host}:{settings.db_port}/"
        f"{database_name}"
    )


DATABASE_URL = _build_database_url(settings.db_name)

engine = create_engine(
    DATABASE_URL,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_database_exists() -> None:
    """Create the configured database if it does not already exist."""
    try:
        with psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        ):
            return
    except psycopg2.OperationalError as db_error:
        error_message = str(db_error)
        if f'database "{settings.db_name}" does not exist' not in error_message:
            raise

    admin_conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname="postgres",
        user=settings.db_user,
        password=settings.db_password,
    )
    try:
        admin_conn.autocommit = True

        with admin_conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (settings.db_name,)
            )
            exists = cursor.fetchone() is not None

            if not exists:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(settings.db_name)
                    )
                )
    finally:
        admin_conn.close()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
