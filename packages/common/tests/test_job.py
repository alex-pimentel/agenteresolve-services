from common.job import Job, JobStatus


def test_job_defaults() -> None:
    job = Job(task_id="t1", tool="translate")
    assert job.status is JobStatus.queued
    assert job.progress == 0
    assert job.result_url is None
    assert job.error is None


def test_job_roundtrip() -> None:
    job = Job(
        task_id="t1",
        tool="translate",
        status=JobStatus.done,
        progress=100,
        result_url="results/x",
    )
    again = Job.model_validate_json(job.model_dump_json())
    assert again == job


def test_job_status_values() -> None:
    assert {s.value for s in JobStatus} == {"queued", "processing", "done", "error"}
