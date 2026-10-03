from common.job import Job, JobStatus
from common.jobs import InMemoryJobStore


def test_create_and_get() -> None:
    store = InMemoryJobStore()
    job = Job(task_id="t1", tool="translate")
    store.create(job)
    assert store.get("t1") == job


def test_get_missing_returns_none() -> None:
    assert InMemoryJobStore().get("x") is None


def test_update_fields() -> None:
    store = InMemoryJobStore()
    store.create(Job(task_id="t1", tool="translate"))
    updated = store.update("t1", status=JobStatus.done, progress=100, result_url="results/x")
    assert updated is not None
    assert updated.status is JobStatus.done
    assert updated.progress == 100
    assert store.get("t1") is not None
    assert store.get("t1").result_url == "results/x"  # type: ignore[union-attr]


def test_update_missing_returns_none() -> None:
    assert InMemoryJobStore().update("x", status=JobStatus.done) is None
