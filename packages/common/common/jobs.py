"""Job state store.

Job state is ephemeral (TTL 24h) and holds no user content. Production uses Redis
(reachable by URL); tests use an in-memory implementation.
"""

from __future__ import annotations

from typing import Protocol

from common.config import get_settings
from common.job import Job


class JobStore(Protocol):
    def create(self, job: Job) -> None: ...

    def get(self, task_id: str) -> Job | None: ...

    def save(self, job: Job) -> None: ...

    def update(self, task_id: str, **fields: object) -> Job | None: ...


class InMemoryJobStore:
    def __init__(self, ttl: int = 86_400) -> None:
        self.ttl = ttl
        self._jobs: dict[str, Job] = {}

    def create(self, job: Job) -> None:
        self._jobs[job.task_id] = job

    def get(self, task_id: str) -> Job | None:
        return self._jobs.get(task_id)

    def save(self, job: Job) -> None:
        self._jobs[job.task_id] = job

    def update(self, task_id: str, **fields: object) -> Job | None:
        job = self._jobs.get(task_id)
        if job is None:
            return None
        updated = job.model_copy(update=fields)
        self._jobs[task_id] = updated
        return updated


class RedisJobStore:
    def __init__(self, redis_url: str, ttl: int = 86_400) -> None:
        import redis

        self.ttl = ttl
        self._client = redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _key(task_id: str) -> str:
        return f"job:{task_id}"

    def create(self, job: Job) -> None:
        self.save(job)

    def get(self, task_id: str) -> Job | None:
        raw = self._client.get(self._key(task_id))
        if raw is None:
            return None
        return Job.model_validate_json(raw)

    def save(self, job: Job) -> None:
        self._client.set(self._key(job.task_id), job.model_dump_json(), ex=self.ttl)

    def update(self, task_id: str, **fields: object) -> Job | None:
        job = self.get(task_id)
        if job is None:
            return None
        updated = job.model_copy(update=fields)
        self.save(updated)
        return updated


def build_job_store() -> JobStore:
    settings = get_settings()
    if settings.redis_url:
        return RedisJobStore(settings.redis_url, ttl=settings.job_ttl_seconds)
    return InMemoryJobStore(ttl=settings.job_ttl_seconds)


_job_store: JobStore | None = None


def get_job_store() -> JobStore:
    global _job_store
    if _job_store is None:
        _job_store = build_job_store()
    return _job_store


def set_job_store(store: JobStore) -> None:
    global _job_store
    _job_store = store


def reset_job_store() -> None:
    global _job_store
    _job_store = None
