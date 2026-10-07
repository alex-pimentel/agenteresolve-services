"""Gateway integration tests: create -> poll per queue with fake providers (no network)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from common.jobs import InMemoryJobStore, set_job_store
from common.providers import factory
from common.providers.base import (
    Detection,
    OcrBlock,
    ProviderUnavailable,
    Transcription,
    TranscriptSegment,
)
from common.providers.llm import FakeLLM
from common.sessions import SessionStore, set_session_store
from common.storage import InMemoryObjectStore, set_object_store
from fastapi.testclient import TestClient
from gateway.auth import get_required_user
from gateway.main import create_app


class _FakeOcr:
    is_remote = True

    def extract(self, data: bytes, *, content_type: str, lang: str | None = None) -> list[OcrBlock]:
        return [OcrBlock(text="hello", bbox=[0, 0, 10, 10], confidence=0.9)]


class _FakeVision:
    is_remote = True

    def caption(self, data: bytes, *, content_type: str) -> str:
        return "a cat"

    def detect(
        self, data: bytes, *, content_type: str, labels: list[str] | None = None
    ) -> list[Detection]:
        return [Detection("person", [0, 0, 10, 10], 0.9)]


class _FakeAudio:
    is_remote = True

    def transcribe(
        self, data: bytes, *, content_type: str, lang: str | None = None
    ) -> Transcription:
        return Transcription(
            text="hi", segments=[TranscriptSegment(0.0, 1.0, "hi")], language=lang or "en"
        )

    def enhance(self, data: bytes, *, content_type: str, mode: str = "denoise") -> bytes:
        return b"enhanced"


class _FakeTts:
    is_remote = True

    def synthesize(self, text: str, **_: object) -> bytes:
        return b"AUDIO"


class _FakeEmbeddings:
    is_remote = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _smart_llm(**kwargs: object) -> str:
    system = str(kwargs.get("system") or "")
    if "pandas" in system or "DataFrame" in system:
        return json.dumps({"code": "len(df)", "explanation": "rows", "chart": {"type": "none"}})
    if "seo" in system.lower() or "SEO" in system:
        return json.dumps({"title": "T", "meta_description": "M", "outline": [], "body": "B"})
    if "classification" in system.lower() or "feedback" in system.lower():
        return json.dumps({"items": [], "summary": "s"})
    if "contract" in system.lower():
        return json.dumps({"risks": [], "summary": ""})
    if "alt-text" in system.lower() or "alt_text" in system.lower() or "accessible alt" in system:
        return json.dumps({"alt": "gato", "caption": [], "tags": []})
    if "summarize transcripts" in system.lower():
        return json.dumps({"summary": "s", "topics": [], "action_items": []})
    if "extract structured" in system.lower():
        return json.dumps({"total": 42})
    if "answer questions" in system.lower():
        return json.dumps({"answer": "ok", "citations": []})
    return json.dumps({"ok": True})


@pytest.fixture
def client() -> Iterator[TestClient]:
    set_object_store(InMemoryObjectStore())
    set_job_store(InMemoryJobStore())
    set_session_store(SessionStore())
    factory.set_llm_provider(FakeLLM(_smart_llm))
    factory.set_provider("ocr", _FakeOcr())
    factory.set_provider("vision", _FakeVision())
    factory.set_provider("audio", _FakeAudio())
    factory.set_provider("tts", _FakeTts())
    factory.set_provider("embeddings", _FakeEmbeddings())

    from worker.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    import worker.tasks  # noqa: F401  (registers worker.run_tool)

    app = create_app()
    app.dependency_overrides[get_required_user] = lambda: {
        "sub": "user_test_123",
        "email": "test@example.com",
    }
    with TestClient(app) as test_client:
        yield test_client
    factory.reset_providers()
    app.dependency_overrides.clear()


def _run(client: TestClient, slug: str, *, method: str = "json", **kwargs: object) -> dict:
    if method == "json":
        created = client.post(f"/api/{slug}/", json=kwargs)
    else:
        files = kwargs.pop("files")
        created = client.post(f"/api/{slug}/", data=kwargs, files=files)
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    status = client.get(f"/api/{slug}/{task_id}")
    assert status.status_code == 200, status.text
    return status.json()


# --- text queue ------------------------------------------------------------------


def test_docuextract_gateway_flow(client: TestClient) -> None:
    factory.set_llm_provider(FakeLLM(json.dumps({"total": 42})))
    job = _run(client, "docuextract", text="Invoice total 42", schema="invoice")
    assert job["status"] == "done"
    assert "results/docuextract" in job["result_url"]


def test_feedback_gateway_flow(client: TestClient) -> None:
    factory.set_llm_provider(
        FakeLLM(json.dumps({"items": [], "summary": "s", "sentiment_counts": {}}))
    )
    job = _run(client, "feedback", text="Great\nBad")
    assert job["status"] == "done"


def test_seo_gateway_flow(client: TestClient) -> None:
    factory.set_llm_provider(FakeLLM(json.dumps({"title": "T"})))
    job = _run(client, "seo", text="solar energy", lang="en", tone="neutral", keyword="solar")
    assert job["status"] == "done"
    assert "results/seo" in job["result_url"]


def test_contracts_gateway_flow(client: TestClient) -> None:
    factory.set_llm_provider(FakeLLM(json.dumps({"risks": [], "summary": ""})))
    job = _run(client, "contracts", text="Contract clause", content_type="text/plain")
    assert job["status"] == "done"


# --- vision queue ----------------------------------------------------------------


def test_ocr_gateway_flow(client: TestClient) -> None:
    job = _run(
        client,
        "ocr",
        method="multipart",
        files={"file": ("scan.png", b"img", "image/png")},
        lang="eng",
    )
    assert job["status"] == "done"
    assert "results/ocr" in job["result_url"]


def test_alttext_gateway_flow(client: TestClient) -> None:
    factory.set_llm_provider(FakeLLM(json.dumps({"alt": "gato", "caption": [], "tags": []})))
    job = _run(
        client, "alttext", method="multipart", files={"file": ("x.png", b"img", "image/png")}
    )
    assert job["status"] == "done"


def test_objectcount_gateway_flow(client: TestClient) -> None:
    job = _run(
        client, "objectcount", method="multipart", files={"file": ("x.png", b"img", "image/png")}
    )
    assert job["status"] == "done"


def test_anonymize_gateway_provider_unavailable_is_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force the redaction step to report a missing local backend, independent of Pillow.
    import worker.handlers.vision as vision_mod

    def _unavailable(*_: object, **__: object) -> bytes:
        raise ProviderUnavailable("no local redaction backend")

    monkeypatch.setattr(vision_mod, "_blur_regions", _unavailable)
    created = client.post("/api/anonymize/", files={"file": ("x.png", b"img", "image/png")})
    assert created.status_code == 202
    task_id = created.json()["task_id"]
    response = client.get(f"/api/anonymize/{task_id}")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "provider_unavailable"


# --- audio queue -----------------------------------------------------------------


def test_transcribe_gateway_flow(client: TestClient) -> None:
    factory.set_llm_provider(
        FakeLLM(json.dumps({"summary": "s", "topics": [], "action_items": []}))
    )
    job = _run(
        client,
        "transcribe",
        method="multipart",
        files={"file": ("a.wav", b"audio", "audio/wav")},
        lang="auto",
        summarize="true",
    )
    assert job["status"] == "done"
    assert "results/transcribe" in job["result_url"]


def test_tts_gateway_flow(client: TestClient) -> None:
    job = _run(client, "tts", text="Hello", lang="en", voice="", speed="1")
    assert job["status"] == "done"
    assert "results/tts" in job["result_url"]


def test_audio_enhance_gateway_flow(client: TestClient) -> None:
    job = _run(
        client,
        "audio-enhance",
        method="multipart",
        files={"file": ("a.wav", b"audio", "audio/wav")},
        mode="denoise",
    )
    assert job["status"] == "done"


# --- sessions --------------------------------------------------------------------


def test_askyourdocs_session_flow(client: TestClient) -> None:
    factory.set_llm_provider(FakeLLM(json.dumps({"answer": "ok", "citations": []})))
    session = client.post("/api/askyourdocs/session")
    assert session.status_code == 200
    session_id = session.json()["session_id"]

    # index a document into the session
    indexed = client.post(
        "/api/askyourdocs/",
        data={"session_id": session_id, "name": "doc"},
        files={"file": ("doc.txt", b"apple banana", "text/plain")},
    )
    assert indexed.status_code == 202
    index_job = client.get(f"/api/askyourdocs/{indexed.json()['task_id']}").json()
    assert index_job["status"] == "done"

    asked = client.post(f"/api/askyourdocs/{session_id}/ask", json={"question": "what fruit?"})
    assert asked.status_code == 202
    ask_job = client.get(f"/api/askyourdocs/{asked.json()['task_id']}").json()
    assert ask_job["status"] == "done"


def test_voicechat_session_endpoint(client: TestClient) -> None:
    response = client.post("/api/voicechat/session", json={"persona": "tutor", "lang": "en"})
    assert response.status_code == 200
    assert response.json()["session_id"]


def test_unknown_session_returns_404(client: TestClient) -> None:
    assert client.get("/api/voicechat/session/nope").status_code == 404


def test_louder_redirects_to_client_side_error(client: TestClient) -> None:
    response = client.post("/api/louder/", json={"text": "x"})
    assert response.status_code == 400
    assert "client-side" in response.json()["detail"].lower()
