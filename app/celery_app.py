from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings


celery_app = Celery(
    "rag_trends",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.ingestion_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.celery_timezone,
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
    task_time_limit=settings.celery_task_time_limit_seconds,
    result_expires=settings.celery_result_expires_seconds,
    worker_pool=settings.celery_worker_pool,
    worker_concurrency=max(1, settings.celery_worker_concurrency),
    worker_max_tasks_per_child=max(1, settings.celery_worker_max_tasks_per_child),
)

if settings.celery_beat_enabled:
    celery_app.conf.beat_schedule = {
        "run-all-sources-pipeline": {
            "task": "app.tasks.ingestion_tasks.run_all_sources_pipeline",
            "schedule": crontab(
                minute=settings.celery_beat_cron_minute,
                hour=settings.celery_beat_cron_hour,
                day_of_week=settings.celery_beat_cron_day_of_week,
                day_of_month=settings.celery_beat_cron_day_of_month,
                month_of_year=settings.celery_beat_cron_month_of_year,
            ),
            "kwargs": {"limit": max(1, settings.celery_beat_auto_limit)},
        }
    }
