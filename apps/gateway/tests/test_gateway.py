import pytest
from common.jobs import InMemoryJobStore, set_job_store
from common.providers import factory
from common.providers.llm import FakeLLM
from common.storage import InMemoryObjectStore, set_object_store
from fastapi.testclient import TestClient
from gateway.main import create_app


@pytest.fixture
def client() -> TestClient:
    object_store = InMemoryObjectStore()
    job_store = InMemoryJobStore()
    set_object_store(object_store)
    set_job_store(job_store)
    factory.set_llm_provider(FakeLLM("Traduzido"))

    from worker.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    import worker.tasks  # noqa: F401  (registers worker.run_tool)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    factory.reset_providers()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_slug_returns_404(client: TestClient) -> None:
    assert client.post("/api/nope/", json={"text": "x"}).status_code == 404
    assert client.get("/api/nope/whatever").status_code == 404


def test_unimplemented_tool_returns_501(client: TestClient) -> None:
    response = client.post("/api/feedback/", json={"text": "x"})
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"].lower()


def test_client_side_tool_returns_501(client: TestClient) -> None:
    response = client.post("/api/louder/", json={"text": "x"})
    assert response.status_code == 501


def test_translate_full_job_flow(client: TestClient) -> None:
    created = client.post(
        "/api/translate/",
        json={"text": "Hello, world!", "target": "pt", "tone": "neutral"},
    )
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "queued"
    task_id = body["task_id"]

    status = client.get(f"/api/translate/{task_id}")
    assert status.status_code == 200
    job = status.json()
    assert job["task_id"] == task_id
    assert job["tool"] == "translate"
    assert job["status"] == "done"
    assert job["progress"] == 100
    assert job["error"] is None
    assert job["result_url"]
    assert "results/translate" in job["result_url"]


def test_get_missing_task_returns_404(client: TestClient) -> None:
    assert client.get("/api/translate/missing-task").status_code == 404


def test_translate_rejects_missing_text(client: TestClient) -> None:
    response = client.post("/api/translate/", json={"target": "pt"})
    assert response.status_code == 422


def test_translate_multipart_upload(client: TestClient) -> None:
    created = client.post(
        "/api/translate/",
        data={"target": "pt", "tone": "neutral"},
        files={"file": ("input.txt", b"Hello from file", "text/plain")},
    )
    assert created.status_code == 202
    task_id = created.json()["task_id"]
    job = client.get(f"/api/translate/{task_id}").json()
    assert job["status"] == "done"
