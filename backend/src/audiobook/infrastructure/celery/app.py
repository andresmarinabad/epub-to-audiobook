"""Celery application — broker and backend both use Redis."""
import os

from celery import Celery

celery_app = Celery(
    "epub2audiobook",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    include=["audiobook.infrastructure.celery.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Each worker processes exactly one task at a time — true parallelism via concurrency
    worker_prefetch_multiplier=1,
    result_expires=86_400,
    task_routes={
        "audiobook.infrastructure.celery.tasks.convert_chapter": {"queue": "chapters"},
        "audiobook.infrastructure.celery.tasks.merge_audiobook": {"queue": "celery"},
    },
)
