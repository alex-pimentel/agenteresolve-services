"""Celery application shared by the gateway (producer) and workers (consumers).

Queues are ``text``, ``vision`` and ``audio``. The gateway selects the queue per tool
using the catalogue, so routing is data-driven and portable.
"""

from celery import Celery

from common.catalog import QUEUES
from common.config import get_settings

TASK_RUN_TOOL = "worker.run_tool"


def create_celery() -> Celery:
    settings = get_settings()
    broker = settings.redis_url or "memory://"
    backend = settings.redis_url or "cache+memory://"

    app = Celery("agenteresolve", broker=broker, backend=backend)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_default_queue="text",
        task_default_exchange="text",
        task_default_routing_key="text",
        task_queues={queue: {"exchange": queue, "routing_key": queue} for queue in QUEUES},
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        timezone="UTC",
        enable_utc=True,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = create_celery()


def enqueue_tool(slug: str, task_id: str, queue: str | None) -> None:
    """Enqueue ``worker.run_tool`` onto ``queue``.

    ``Celery.send_task`` ignores ``task_always_eager``, so in test/eager mode we execute
    the registered task synchronously instead.
    """
    kwargs = {"slug": slug, "task_id": task_id}
    if celery_app.conf.task_always_eager:
        task = celery_app.tasks.get(TASK_RUN_TOOL)
        if task is None:
            raise RuntimeError(
                f"Task '{TASK_RUN_TOOL}' is not registered; import 'worker.tasks' first"
            )
        task.apply(kwargs=kwargs)
        return
    celery_app.send_task(TASK_RUN_TOOL, kwargs=kwargs, queue=queue)
