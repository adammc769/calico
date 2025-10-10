"""Celery application initialization."""
from __future__ import annotations

import os

from celery import Celery

from .config import get_settings

settings = get_settings()

celery_app = Celery(
    "calico",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_default_queue=os.getenv("CELERY_DEFAULT_QUEUE", "default"),
    task_routes={
        "calico.workflow.tasks.collect_dom_units": {"queue": "scraping"},
        "calico.workflow.tasks.run_agent_session": {"queue": "agents"},
        "calico.workflow.tasks.orchestrate_workflow": {"queue": "workflow"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("CELERY_TIMEZONE", "UTC"),
    enable_utc=True,
)

celery_app.autodiscover_tasks(["calico.workflow.tasks"])
