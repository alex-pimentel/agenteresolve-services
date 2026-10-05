"""Tests for centralized login: gateway session tokens issued from Clerk identity."""

from collections.abc import Iterator

import pytest
from common.config import get_settings
from common.jobs import InMemoryJobStore, set_job_store
from common.providers import factory
from common.providers.llm import FakeLLM
from common.service_tokens import (
    ServiceTokenError,
    issue_token,
    revoke_token,
    verify_token,
)
from common.storage import InMemoryObjectStore, set_object_store
from fastapi.testclient import TestClient
from gateway.auth import get_required_user
from gateway.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    set_object_store(InMemoryObjectStore())
    set_job_store(InMemoryJobStore())
    factory.set_llm_provider(FakeLLM("Traduzido"))

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


@pytest.fixture
def session_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    from common.config import get_settings

    monkeypatch.setenv("GATEWAY_SESSION_SECRET", "test-secret-123")
    get_settings.cache_clear()
    yield "test-secret-123"
    get_settings.cache_clear()


def test_session_issue_requires_configured_secret(client: TestClient) -> None:
    response = client.post("/api/auth/session")
    assert response.status_code == 503


def test_full_session_flow(client: TestClient, session_secret: str) -> None:
    issued = client.post("/api/auth/session")
    assert issued.status_code == 200
    body = issued.json()
    assert body["token_type"] == "Bearer"
    assert body["clerk_id"] == "user_test_123"
    assert body["expires_at"] > 0
    token = body["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["clerk_id"] == "user_test_123"

    created = client.post(
        "/api/translate/",
        json={"text": "Hello", "target": "pt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 202
    job = client.get(
        f"/api/translate/{created.json()['task_id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert job["status"] == "done"
    assert job["owner_sub"] == "user_test_123"


def test_expired_session_token_rejected(
    client: TestClient, session_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import jwt

    stale = jwt.encode(
        {
            "iss": "agenteresolve-gateway",
            "typ": "gateway-session",
            "sub": "u",
            "jti": "x",
            "iat": 1,
            "exp": 2,
        },
        session_secret,
        algorithm="HS256",
    )
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    client.app.dependency_overrides.clear()
    try:
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {stale}"})
        assert response.status_code == 401
    finally:
        get_settings.cache_clear()
        client.app.dependency_overrides[get_required_user] = lambda: {
            "sub": "user_test_123",
            "email": "test@example.com",
        }


def test_issue_verify_roundtrip(session_secret: str) -> None:
    token, expires_at, jti = issue_token(clerk_id="u1", email="a@b.c")
    assert expires_at > 0 and jti
    claims = verify_token(token)
    assert claims["sub"] == "u1"
    assert claims["email"] == "a@b.c"


def test_tampered_token_rejected(session_secret: str) -> None:
    token, _, _ = issue_token(clerk_id="u1")
    with pytest.raises(ServiceTokenError):
        verify_token(token + "tampered")


def test_logout_revokes_with_denylist(
    client: TestClient, session_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import common.service_tokens as st

    class FakeRedis:
        def __init__(self) -> None:
            self.data: dict[str, str] = {}

        def get(self, key: str) -> str | None:
            return self.data.get(key)

        def set(self, key: str, value: str, ex: int | None = None) -> bool:
            self.data[key] = value
            return True

    fake = FakeRedis()
    monkeypatch.setattr(st, "_denylist", lambda: fake)
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    client.app.dependency_overrides.clear()
    try:
        token, _, _ = issue_token(clerk_id="u1")
        assert revoke_token(token) is True
        with pytest.raises(ServiceTokenError):
            verify_token(token)

        # Exercise the real auth path (no overrides): refresh via gateway token.
        seed, _, _ = issue_token(clerk_id="u1", email="a@b.c")
        issued = client.post(
            "/api/auth/session", headers={"Authorization": f"Bearer {seed}"}
        ).json()["access_token"]
        logged = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {issued}"})
        assert logged.json() == {"status": "ok", "revoked": True}
        assert (
            client.get("/api/auth/me", headers={"Authorization": f"Bearer {issued}"}).status_code
            == 401
        )
    finally:
        get_settings.cache_clear()
        client.app.dependency_overrides[get_required_user] = lambda: {
            "sub": "user_test_123",
            "email": "test@example.com",
        }


def test_logout_without_redis_is_best_effort(
    client: TestClient, session_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import common.service_tokens as st

    monkeypatch.setattr(st, "_denylist", lambda: None)
    issued = client.post("/api/auth/session").json()["access_token"]
    logged = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {issued}"})
    assert logged.json() == {"status": "ok", "revoked": False}
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {issued}"}).status_code == 200
    )
