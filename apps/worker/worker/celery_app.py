"""Celery application used by the worker containers."""

from common.queue import TASK_RUN_TOOL, celery_app

from worker import tasks  # noqa: F401 - registers worker.run_tool on the app

__all__ = ["TASK_RUN_TOOL", "celery_app", "tasks"]
