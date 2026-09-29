"""Celery worker and schedule for background jobs.

celery -A app.worker worker --beat --loglevel=info --pool=solo   # --pool=solo on Windows
"""

import asyncio

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.pipeline import jobs

settings = get_settings()

celery_app = Celery("cinescope", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(timezone="UTC", task_acks_late=True, worker_prefetch_multiplier=1)

celery_app.conf.beat_schedule = {
    "tmdb-lists-every-6h": {
        "task": "pipeline.refresh_lists",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "tmdb-changes-daily": {
        "task": "pipeline.refresh_changes",
        "schedule": crontab(minute=30, hour=3),
    },
    "reminders-every-15m": {
        "task": "reminders.send_due",
        "schedule": crontab(minute="*/15"),
    },
    "wikipedia-daily": {"task": "pipeline.enrich_wikipedia", "schedule": crontab(minute=0, hour=4)},
}


@celery_app.task(name="pipeline.refresh_lists")
def refresh_lists() -> dict:
    return asyncio.run(jobs.refresh_lists())


@celery_app.task(name="pipeline.refresh_changes")
def refresh_changes(days: int = 1) -> dict:
    return asyncio.run(jobs.refresh_changes(days))


@celery_app.task(name="pipeline.enrich_wikipedia")
def enrich_wikipedia() -> dict:
    return asyncio.run(jobs.enrich_wikipedia())


@celery_app.task(name="reminders.send_due")
def send_due_reminders() -> dict:
    return asyncio.run(jobs.send_due_reminders())
