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
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gateway.auth import get_required_user
from gateway.main import create_app


@pytest.fixture
def app() -> Iterator[FastAPI]:
    set_object_store(InMemoryObjectStore())
    set_job_store(InMemoryJobStore())
    factory.set_llm_provider(FakeLLM("Traduzido"))

    from worker.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    import worker.tasks  # noqa: F401  (registers worker.run_tool)

    application = create_app()
    application.dependency_overrides[get_required_user] = lambda: {
        "sub": "user_test_123",
        "email": "test@example.com",
    }
    yield application
    factory.reset_providers()
    application.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
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
    app: FastAPI, client: TestClient, session_secret: str, monkeypatch: pytest.MonkeyPatch
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
    app.dependency_overrides.clear()
    try:
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {stale}"})
        assert response.status_code == 401
    finally:
        get_settings.cache_clear()
        app.dependency_overrides[get_required_user] = lambda: {
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
    app: FastAPI, client: TestClient, session_secret: str, monkeypatch: pytest.MonkeyPatch
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
    app.dependency_overrides.clear()
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
        app.dependency_overrides[get_required_user] = lambda: {
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


def test_verify_without_jwks_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    import gateway.auth as auth_module
    from fastapi import HTTPException

    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc_info:
            auth_module._verify("anything")
        assert exc_info.value.status_code == 401
    finally:
        get_settings.cache_clear()


class _FakeJwksClient:
    def __init__(self, url: str) -> None:
        self.url = url

    def get_signing_key_from_jwt(self, token: str) -> object:
        from types import SimpleNamespace

        assert token == "clerk-jwt"
        return SimpleNamespace(key="signing-key")


def _mock_clerk_jwks(monkeypatch: pytest.MonkeyPatch, decode: object) -> None:
    import gateway.auth as auth_module

    monkeypatch.setenv("CLERK_JWKS_URL", "https://clerk.test/.well-known/jwks.json")
    get_settings.cache_clear()
    monkeypatch.setattr(auth_module, "PyJWKClient", _FakeJwksClient)
    monkeypatch.setattr(auth_module.jwt, "decode", decode)


def test_verify_clerk_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import gateway.auth as auth_module

    _mock_clerk_jwks(monkeypatch, lambda *args, **kwargs: {"sub": "clerk_1"})
    try:
        assert auth_module._verify("clerk-jwt") == {"sub": "clerk_1"}
    finally:
        get_settings.cache_clear()


def test_verify_invalid_clerk_token_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    import gateway.auth as auth_module
    from fastapi import HTTPException
    from jwt import PyJWTError

    def boom(*args: object, **kwargs: object) -> object:
        raise PyJWTError("bad signature")

    _mock_clerk_jwks(monkeypatch, boom)
    try:
        with pytest.raises(HTTPException) as exc_info:
            auth_module._verify("clerk-jwt")
        assert exc_info.value.status_code == 401
    finally:
        get_settings.cache_clear()


def test_optional_user_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    import gateway.auth as auth_module

    assert auth_module.get_optional_user(None) is None

    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    get_settings.cache_clear()
    try:
        assert auth_module.get_optional_user("Bearer whatever") is None
    finally:
        get_settings.cache_clear()

    _mock_clerk_jwks(monkeypatch, lambda *args, **kwargs: {"sub": "clerk_1"})
    try:
        assert auth_module.get_optional_user("Bearer clerk-jwt") == {"sub": "clerk_1"}
    finally:
        get_settings.cache_clear()


def test_required_user_local_dev_without_clerk(monkeypatch: pytest.MonkeyPatch) -> None:
    import gateway.auth as auth_module

    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    get_settings.cache_clear()
    try:
        assert auth_module.get_required_user(None) == {"sub": "local-dev", "email": None}
        assert auth_module.get_required_user("Bearer whatever") == {
            "sub": "local-dev",
            "email": None,
        }
    finally:
        get_settings.cache_clear()


def test_required_user_accepts_clerk_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    import gateway.auth as auth_module

    monkeypatch.setenv("AUTH_REQUIRED", "true")
    _mock_clerk_jwks(monkeypatch, lambda *args, **kwargs: {"sub": "clerk_9"})
    try:
        assert auth_module.get_required_user("Bearer clerk-jwt") == {"sub": "clerk_9"}
    finally:
        get_settings.cache_clear()


def test_logout_requires_authorization(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 401


def test_session_balance_degraded_when_billing_down(
    client: TestClient, session_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from common.billing import BillingUnavailable

    from common import billing as billing_module

    class _DownBilling:
        def enabled(self) -> bool:
            return True

        def balance(self, **kwargs: object) -> int:
            raise BillingUnavailable("down")

    monkeypatch.setattr(billing_module, "_billing_client", _DownBilling())
    try:
        body = client.post("/api/auth/session").json()
        assert body["balance"] is None
    finally:
        billing_module.reset_billing_client()


def test_verify_rejects_wrong_token_type(session_secret: str) -> None:
    import jwt

    other = jwt.encode(
        {
            "iss": "agenteresolve-gateway",
            "typ": "not-a-session",
            "sub": "u",
            "jti": "x",
            "iat": 1,
            "exp": 9999999999,
        },
        session_secret,
        algorithm="HS256",
    )
    with pytest.raises(ServiceTokenError):
        verify_token(other)


def test_denylist_best_effort_on_lookup_failure(
    session_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import common.service_tokens as st

    class _FlakyRedis:
        def get(self, key: str) -> str:
            raise RuntimeError("redis down")

    monkeypatch.setattr(st, "_denylist", lambda: _FlakyRedis())
    token, _, _ = issue_token(clerk_id="u1")
    assert verify_token(token)["sub"] == "u1"


def test_denylist_returns_none_without_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import common.service_tokens as st

    monkeypatch.delenv("REDIS_URL", raising=False)
    get_settings.cache_clear()
    try:
        assert st._denylist() is None
    finally:
        get_settings.cache_clear()


def test_denylist_handles_redis_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    import common.service_tokens as st

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    monkeypatch.setitem(sys.modules, "redis", None)
    try:
        assert st._denylist() is None
    finally:
        get_settings.cache_clear()


def test_revoke_invalid_or_foreign_tokens(session_secret: str) -> None:
    import jwt

    assert revoke_token("not-a-token") is False

    foreign = jwt.encode(
        {"iss": "someone-else", "typ": "whatever", "jti": "x", "exp": 9999999999},
        "other-secret",
        algorithm="HS256",
    )
    assert revoke_token(foreign) is False


def test_revoke_handles_denylist_failure(
    session_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import common.service_tokens as st

    class _FlakyRedis:
        def set(self, key: str, value: str, ex: int | None = None) -> bool:
            raise RuntimeError("redis down")

    monkeypatch.setattr(st, "_denylist", lambda: _FlakyRedis())
    token, _, _ = issue_token(clerk_id="u1")
    assert revoke_token(token) is False


def test_looks_like_service_token_rejects_garbage() -> None:
    import common.service_tokens as st

    assert st.looks_like_service_token("not-a-token") is False
    assert st.looks_like_service_token("") is False
