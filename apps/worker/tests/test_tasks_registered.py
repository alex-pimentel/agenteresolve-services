"""Regression: the deployed worker entrypoint must register worker.run_tool.

Production symptom: workers booted "ready" with an empty task registry, so every
enqueued job died with ``Received unregistered task of type 'worker.run_tool'``
and tool frontends polled until timeout. Importing the celery entrypoint exactly
like ``celery -A worker.celery_app`` does must leave the task registered.
"""

import worker.celery_app  # noqa: F401 - entrypoint import under test
from common.queue import TASK_RUN_TOOL, celery_app


def test_run_tool_registered_on_entrypoint_import() -> None:
    assert TASK_RUN_TOOL in celery_app.tasks
    assert celery_app.tasks[TASK_RUN_TOOL].name == TASK_RUN_TOOL
