"""Job execution pipeline shared by all worker queues."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from common.billing import BillingError, get_billing_client
from common.job import Job, JobStatus
from common.jobs import get_job_store
from common.providers import factory
from common.providers.base import ProviderUnavailable
from common.storage import ObjectStore, get_object_store

from worker.handlers import get_handler
from worker.handlers.base import HandlerContext

logger = logging.getLogger(__name__)


def _payload_key(slug: str, task_id: str) -> str:
    return f"uploads/{slug}/{task_id}/payload.json"


def _load_payload(object_store: ObjectStore, slug: str, task_id: str) -> dict[str, Any]:
    raw = object_store.get_bytes(_payload_key(slug, task_id))
    payload: dict[str, Any] = json.loads(raw)
    return payload


def _build_context(job: Job, payload: dict[str, Any], object_store: ObjectStore) -> HandlerContext:
    from common.config import get_settings

    translate_model = get_settings().llm_model_translate
    return HandlerContext(
        task_id=job.task_id,
        slug=job.tool,
        object_store=object_store,
        input_key=payload["input_key"],
        params=payload.get("params", {}),
        llm=factory.get_llm_provider(tool=job.tool),
        translate_llm=(
            factory.get_llm_provider_for_model(translate_model) if translate_model else None
        ),
        embeddings=factory.get_embeddings_provider(),
        ocr=factory.get_ocr_provider(),
        vision=factory.get_vision_provider(),
        audio=factory.get_audio_provider(),
        tts=factory.get_tts_provider(),
    )


def process_job(slug: str, task_id: str) -> Job:
    """Run a job synchronously and return the updated :class:`Job`.

    Errors are captured on the job (status ``error``) rather than propagated, so a single
    bad payload never crashes the worker.
    """
    job_store = get_job_store()
    job = job_store.get(task_id)
    if job is None:
        raise KeyError(f"Job '{task_id}' not found")

    job_store.update(task_id, status=JobStatus.processing, progress=5)
    object_store = get_object_store()
    started = time.monotonic()

    try:
        handler = get_handler(slug)
        payload = _load_payload(object_store, slug, task_id)
        context = _build_context(job, payload, object_store)
        result = handler(context)
        object_store.put_bytes(result.key, result.data, result.content_type)
        updated = job_store.update(
            task_id,
            status=JobStatus.done,
            progress=100,
            result_url=result.key,
            error=None,
            error_code=None,
        )
        _settle(task_id, success=True, latency_ms=int((time.monotonic() - started) * 1000))
    except ProviderUnavailable as exc:
        logger.warning("Tool '%s' job '%s' has no provider: %s", slug, task_id, exc)
        updated = job_store.update(
            task_id,
            status=JobStatus.error,
            error=f"provider_unavailable: {exc}",
            error_code="provider_unavailable",
        )
        _settle(task_id, success=False, reason="provider_unavailable")
    except Exception as exc:  # noqa: BLE001 - reported on the job
        logger.exception("Tool '%s' job '%s' failed", slug, task_id)
        updated = job_store.update(
            task_id,
            status=JobStatus.error,
            error=f"{type(exc).__name__}: {exc}",
            error_code="processing_error",
        )
        _settle(task_id, success=False, reason="processing_error")

    if updated is None:
        raise KeyError(f"Job '{task_id}' disappeared during processing")
    return updated


def _settle(
    task_id: str, *, success: bool, latency_ms: int | None = None, reason: str = "failed"
) -> None:
    """Commit successful calls, refund failed ones. Failed calls are never charged.

    Settlement failures are logged but never fail the job itself; the reserved
    credits stay visible in the ledger for reconciliation.
    """
    billing = get_billing_client()
    if not billing.enabled():
        return
    try:
        if success:
            billing.commit(task_id=task_id, status_code=200, latency_ms=latency_ms)
        else:
            billing.refund(task_id=task_id, reason=reason)
    except BillingError as exc:
        logger.error("Billing settlement failed for job '%s': %s", task_id, exc)
