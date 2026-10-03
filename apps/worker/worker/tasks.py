"""Celery tasks.

A single ``worker.run_tool`` task is registered on every worker; the gateway routes each
job to the ``text``/``vision``/``audio`` queue based on the tool catalogue, and each
worker container consumes only its queue.
"""

from typing import Any

from common.queue import TASK_RUN_TOOL, celery_app

from worker.runner import process_job


@celery_app.task(name=TASK_RUN_TOOL, bind=True, acks_late=True)
def run_tool(self: Any, slug: str, task_id: str) -> dict[str, Any]:
    job = process_job(slug, task_id)
    return job.model_dump(mode="json")
