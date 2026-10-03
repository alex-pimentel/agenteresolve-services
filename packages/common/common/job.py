"""Canonical job model shared by the gateway and workers."""

from enum import StrEnum

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    done = "done"
    error = "error"


class Job(BaseModel):
    task_id: str
    tool: str
    status: JobStatus = JobStatus.queued
    progress: int = Field(default=0, ge=0, le=100)
    result_url: str | None = None
    error: str | None = None
