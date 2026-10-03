"""Job creation: persist input/payload to object storage and enqueue the worker task."""

from __future__ import annotations

import json
import uuid
from typing import Any

from common.catalog import get_tool
from common.job import Job
from common.jobs import get_job_store
from common.queue import enqueue_tool
from common.storage import get_object_store


def create_tool_job(
    *,
    slug: str,
    params: dict[str, Any],
    content: bytes,
    content_type: str,
) -> Job:
    spec = get_tool(slug)
    task_id = uuid.uuid4().hex
    input_key = f"uploads/{slug}/{task_id}/input"
    payload_key = f"uploads/{slug}/{task_id}/payload.json"

    object_store = get_object_store()
    object_store.put_bytes(input_key, content, content_type)
    object_store.put_bytes(
        payload_key,
        json.dumps({"input_key": input_key, "content_type": content_type, "params": params}).encode(
            "utf-8"
        ),
        "application/json",
    )

    job = Job(task_id=task_id, tool=slug)
    get_job_store().create(job)

    enqueue_tool(slug, task_id, spec.queue)
    return job
