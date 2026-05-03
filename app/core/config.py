from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Trends API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    source_preview_max_items: int = 20
    external_request_timeout_seconds: float = 15.0
    google_trends_pn: str = "india"
    ingestion_default_limit: int = 15

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "rag_trends_db"

    # LLM - Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    # RAG retrieval thresholds - tuned for accurate contextual matching
    # Strict mode: high confidence that chunks are relevant
    rag_min_similarity_for_context: float = 0.20  # Semantic similarity (0.0-1.0, lower=more lenient)
    rag_min_lexical_overlap_for_context: float = 0.08  # Keyword overlap ratio (0.0-1.0)
    rag_min_hybrid_score_for_context: float = 0.22  # 75% semantic + 25% lexical
    # Fuzzy matching for similar terms
    rag_enable_fuzzy_lexical_match: bool = True
    rag_fuzzy_token_match_ratio: float = 0.84  # SequenceMatcher similarity for typos/variants
    # Strong semantic signal (can pass without lexical match)
    rag_strong_similarity_override: float = 0.36
    # Relaxed mode: fallback when strict mode finds insufficient results
    rag_enable_relaxed_fallback: bool = True
    rag_relaxed_min_similarity_for_context: float = 0.12
    rag_relaxed_min_lexical_overlap_for_context: float = 0.03
    rag_relaxed_min_hybrid_score_for_context: float = 0.14
    rag_min_relevant_chunks: int = 1
    rag_max_sources_for_summary: int = 5
    rag_max_chunks_per_source: int = 2

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_timezone: str = "UTC"
    celery_task_soft_time_limit_seconds: int = 600
    celery_task_time_limit_seconds: int = 900
    celery_result_expires_seconds: int = 3600
    celery_worker_pool: str = "solo"
    celery_worker_concurrency: int = 1
    celery_worker_max_tasks_per_child: int = 20
    celery_beat_enabled: bool = True
    celery_beat_cron_minute: str = "*/30"
    celery_beat_cron_hour: str = "*"
    celery_beat_cron_day_of_week: str = "*"
    celery_beat_cron_day_of_month: str = "*"
    celery_beat_cron_month_of_year: str = "*"
    celery_beat_auto_limit: int = 15
    celery_auto_sources_csv: str = (
        "google_news_ai,google_news_global,hackernews_topstories,google_trends_daily"
    )

    # Embedding runtime safety knobs
    tokenizers_parallelism: str = "false"
    omp_num_threads: int = 1
    mkl_num_threads: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
