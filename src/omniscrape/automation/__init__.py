# src/omniscrape/automation/__init__.py
from .webhook import send_webhook
from .scheduler import (
    create_job,
    list_jobs,
    get_job,
    toggle_job_status,
    toggle_job,
    update_job,
    delete_job,
    get_job_logs,
    execute_job_pipeline,
    trigger_job_now,
    BackgroundScheduler,
    get_scheduler
)

__all__ = [
    "send_webhook",
    "create_job",
    "list_jobs",
    "get_job",
    "toggle_job_status",
    "update_job",
    "delete_job",
    "get_job_logs",
    "execute_job_pipeline",
    "trigger_job_now",
    "BackgroundScheduler",
    "get_scheduler"
]
