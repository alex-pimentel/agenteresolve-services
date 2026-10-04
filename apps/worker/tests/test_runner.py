import json
from collections.abc import Iterator

import pytest
from common.job import Job, JobStatus
from common.jobs import InMemoryJobStore, set_job_store
from common.providers import factory
from common.providers.llm import FakeLLM
from common.storage import InMemoryObjectStore, set_object_store
from worker.runner import process_job


@pytest.fixture
def stores() -> Iterator[tuple[InMemoryJobStore, InMemoryObjectStore]]:
    job_store = InMemoryJobStore()
    object_store = InMemoryObjectStore()
    set_job_store(job_store)
    set_object_store(object_store)
    factory.set_llm_provider(FakeLLM("Traduzido"))
    yield job_store, object_store
    factory.reset_providers()


def _seed(object_store: InMemoryObjectStore, task_id: str, target: str = "pt") -> None:
    object_store.put_bytes(f"uploads/translate/{task_id}/input", b"Hello")
    payload = {
        "input_key": f"uploads/translate/{task_id}/input",
        "content_type": "text/plain",
        "params": {"target": target},
    }
    object_store.put_bytes(
        f"uploads/translate/{task_id}/payload.json", json.dumps(payload).encode()
    )


def test_process_job_translate_done(
    stores: tuple[InMemoryJobStore, InMemoryObjectStore],
) -> None:
    job_store, object_store = stores
    _seed(object_store, "t1")
    job_store.create(Job(task_id="t1", tool="translate"))

    job = process_job("translate", "t1")

    assert job.status is JobStatus.done
    assert job.progress == 100
    assert job.result_url == "results/translate/t1/result.txt"
    assert object_store.get_bytes(job.result_url) == b"Traduzido"


def test_process_job_marks_error_on_bad_input(
    stores: tuple[InMemoryJobStore, InMemoryObjectStore],
) -> None:
    job_store, object_store = stores
    _seed(object_store, "t2", target="klingon")
    job_store.create(Job(task_id="t2", tool="translate"))

    job = process_job("translate", "t2")

    assert job.status is JobStatus.error
    assert job.error
    assert job_store.get("t2").status is JobStatus.error  # type: ignore[union-attr]


def test_process_job_missing_payload_marks_error(
    stores: tuple[InMemoryJobStore, InMemoryObjectStore],
) -> None:
    job_store, _ = stores
    job_store.create(Job(task_id="t3", tool="seo"))

    job = process_job("seo", "t3")

    assert job.status is JobStatus.error
    assert job.error_code == "processing_error"
