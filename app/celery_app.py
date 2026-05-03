from __future__ import annotations

import ssl

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings


def _cron_value(value: str | None) -> str:
    cleaned_value = (value or "").strip()
    if not cleaned_value:
        return "*"
    if cleaned_value.startswith("/"):
        return f"*{cleaned_value}"
    return cleaned_value


def _ssl_cert_reqs(value: str) -> ssl.VerifyMode:
    normalized = value.strip().lower()
    if normalized == "none":
        return ssl.CERT_NONE
    if normalized == "optional":
        return ssl.CERT_OPTIONAL
    return ssl.CERT_REQUIRED


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
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=max(1, settings.celery_broker_connection_timeout_seconds),
    broker_transport_options={
        "socket_connect_timeout": max(1, settings.celery_broker_socket_timeout_seconds),
        "socket_timeout": max(1, settings.celery_broker_socket_timeout_seconds),
        "retry_on_timeout": True,
    },
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

if settings.celery_broker_url.lower().startswith("rediss://"):
    celery_app.conf.broker_use_ssl = {
        "ssl_cert_reqs": _ssl_cert_reqs(settings.celery_broker_ssl_cert_reqs)
    }

if settings.celery_result_backend.lower().startswith("rediss://"):
    celery_app.conf.redis_backend_use_ssl = {
        "ssl_cert_reqs": _ssl_cert_reqs(settings.celery_broker_ssl_cert_reqs)
    }

if settings.celery_beat_enabled:
    celery_app.conf.beat_schedule = {
        "run-all-sources-pipeline": {
            "task": "app.tasks.ingestion_tasks.run_all_sources_pipeline",
            "schedule": crontab(
                minute=_cron_value(settings.celery_beat_cron_minute),
                hour=_cron_value(settings.celery_beat_cron_hour),
                day_of_week=_cron_value(settings.celery_beat_cron_day_of_week),
                day_of_month=_cron_value(settings.celery_beat_cron_day_of_month),
                month_of_year=_cron_value(settings.celery_beat_cron_month_of_year),
            ),
            "kwargs": {"limit": max(1, settings.celery_beat_auto_limit)},
        }
    }
