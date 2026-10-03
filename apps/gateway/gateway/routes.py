"""HTTP API routes for the gateway."""

from __future__ import annotations

from typing import Any

from common.config import get_settings
from common.job import JobStatus
from common.jobs import get_job_store
from common.storage import get_object_store
from fastapi import APIRouter, Depends, HTTPException, Request, status

from gateway.auth import get_optional_user
from gateway.jobs import create_tool_job
from gateway.registry import resolve

router = APIRouter()


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/{slug}/", status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
async def create_job(
    slug: str,
    request: Request,
    _user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, str]:
    spec = resolve(slug)
    if not spec.implemented:
        reason = (
            "client-side tool; no gateway endpoint"
            if spec.category == "client"
            else "registered but not implemented yet"
        )
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Tool '{slug}' is {reason}.",
        )

    params, content, content_type = await _parse_input(request, spec.max_bytes)
    job = create_tool_job(slug=slug, params=params, content=content, content_type=content_type)
    return {"task_id": job.task_id, "tool": slug, "status": job.status.value}


@router.get("/api/{slug}/{task_id}", tags=["jobs"])
def get_job(
    slug: str,
    task_id: str,
    _user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    resolve(slug)
    job_store = get_job_store()
    job = job_store.get(task_id)
    if job is None or job.tool != slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found for tool '{slug}'",
        )

    if job.status is JobStatus.done and job.result_url:
        settings = get_settings()
        try:
            presigned = get_object_store().presigned_get_url(
                job.result_url, settings.r2_presign_seconds
            )
            job = job.model_copy(update={"result_url": presigned})
        except Exception:  # noqa: BLE001 - fall back to the stored key
            pass

    return job.model_dump(mode="json")


async def _parse_input(request: Request, max_bytes: int) -> tuple[dict[str, Any], bytes, str]:
    content_type_header = request.headers.get("content-type", "")
    text: str
    params: dict[str, Any]

    if content_type_header.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        params = {
            key: str(value)
            for key, value in form.items()
            if key != "file" and not hasattr(value, "filename")
        }
        if upload is not None and not isinstance(upload, str):
            content = await upload.read()
            content_type = upload.content_type or "application/octet-stream"
        elif form.get("text") is not None:
            content = str(form["text"]).encode("utf-8")
            content_type = "text/plain; charset=utf-8"
        else:
            raise HTTPException(
                status_code=422,
                detail="Multipart body must include 'file' or 'text'",
            )
    else:
        try:
            payload = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail="Body must be JSON or multipart/form-data",
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=422,
                detail="JSON body must be an object",
            )
        text_value = payload.get("text")
        if not text_value or not isinstance(text_value, str):
            raise HTTPException(
                status_code=422,
                detail="Field 'text' is required",
            )
        text = text_value
        params = {key: value for key, value in payload.items() if key != "text"}
        content = text.encode("utf-8")
        content_type = "text/plain; charset=utf-8"

    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Input too large: {len(content)} bytes exceeds limit of {max_bytes}",
        )
    return params, content, content_type
