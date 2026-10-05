"""Tests for centralized billing: reserve on creation, settle on completion."""

from collections.abc import Iterator

import httpx
import pytest
from common.billing import (
    BillingClient,
    BillingUnavailable,
    DisabledBillingClient,
    InsufficientCredits,
    reset_billing_client,
    set_billing_client,
)
from common.jobs import InMemoryJobStore, set_job_store
from common.providers import factory
from common.providers.llm import FakeLLM
from common.storage import InMemoryObjectStore, set_object_store
from fastapi.testclient import TestClient
from gateway.auth import get_required_user
from gateway.main import create_app


class FakeBillingClient:
    """Records reserve/commit/refund calls instead of hitting Laravel."""

    def __init__(self, cost: int = 2) -> None:
        self.cost = cost
        self.reserved: list[str] = []
        self.committed: list[str] = []
        self.refunded: list[str] = []

    def enabled(self) -> bool:
        return True

    def reserve(self, **kwargs: object) -> object:
        from common.billing import Reservation

        task_id = str(kwargs.get("task_id", ""))
        self.reserved.append(task_id)
        return Reservation(task_id=task_id, cost=self.cost, balance=48)

    def commit(self, **kwargs: object) -> int:
        self.committed.append(str(kwargs.get("task_id", "")))
        return self.cost

    def refund(self, **kwargs: object) -> None:
        self.refunded.append(str(kwargs.get("task_id", "")))


@pytest.fixture
def billing() -> FakeBillingClient:
    fake = FakeBillingClient()
    set_billing_client(fake)
    return fake


@pytest.fixture
def client(billing: FakeBillingClient) -> Iterator[TestClient]:
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
    reset_billing_client()


def test_create_reserves_credits_and_commits_on_success(
    client: TestClient, billing: FakeBillingClient
) -> None:
    created = client.post("/api/translate/", json={"text": "Hello", "target": "pt"})
    assert created.status_code == 202
    task_id = created.json()["task_id"]

    assert billing.reserved == [task_id]

    job = client.get(f"/api/translate/{task_id}").json()
    assert job["status"] == "done"
    assert job["owner_sub"] == "user_test_123"
    assert job["cost_units"] == 2

    # Eager worker settles synchronously after the job completes.
    assert billing.committed == [task_id]
    assert billing.refunded == []


def test_insufficient_credits_returns_402(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from common import billing as billing_module

    def boom(**kwargs: object) -> object:
        raise InsufficientCredits(balance=0, required=2)

    monkeypatch.setattr(billing_module.get_billing_client(), "reserve", boom)

    response = client.post("/api/translate/", json={"text": "Hello", "target": "pt"})
    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "insufficient_credits"


def test_billing_outage_fails_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from common import billing as billing_module

    def boom(**kwargs: object) -> object:
        raise BillingUnavailable("down")

    monkeypatch.setattr(billing_module.get_billing_client(), "reserve", boom)

    response = client.post("/api/translate/", json={"text": "Hello", "target": "pt"})
    assert response.status_code == 503


def test_users_cannot_poll_each_others_jobs(client: TestClient) -> None:
    created = client.post("/api/translate/", json={"text": "Hello", "target": "pt"})
    task_id = created.json()["task_id"]

    client.app.dependency_overrides[get_required_user] = lambda: {"sub": "intruder"}
    try:
        assert client.get(f"/api/translate/{task_id}").status_code == 404
    finally:
        client.app.dependency_overrides[get_required_user] = lambda: {
            "sub": "user_test_123",
            "email": "test@example.com",
        }


def test_failed_job_is_refunded(
    client: TestClient, billing: FakeBillingClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import worker.runner as runner_module

    def fail(slug: object) -> object:
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(runner_module, "get_handler", fail)

    created = client.post("/api/translate/", json={"text": "Hello", "target": "pt"})
    task_id = created.json()["task_id"]

    job = client.get(f"/api/translate/{task_id}").json()
    assert job["status"] == "error"
    assert billing.refunded == [task_id]
    assert billing.committed == []


def test_disabled_billing_is_noop() -> None:
    client = DisabledBillingClient()
    assert client.enabled() is False
    assert client.commit(task_id="x") == 0
    assert client.refund(task_id="x") is None


def _mock_billing_client(handler: httpx.MockTransport) -> BillingClient:
    return BillingClient(
        base_url="https://billing.test",
        service_token="secret",
        transport=handler,
    )


def test_billing_client_reserve_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Service-Token"] == "secret"
        return httpx.Response(201, json={"task_id": "t1", "cost": 3, "balance": 47})

    client = _mock_billing_client(httpx.MockTransport(handler))
    reservation = client.reserve(clerk_id="u1", email=None, tool="translate", task_id="t1")
    assert (reservation.task_id, reservation.cost, reservation.balance) == ("t1", 3, 47)


def test_billing_client_reserve_402() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"balance": 0, "required": 3})

    client = _mock_billing_client(httpx.MockTransport(handler))
    with pytest.raises(InsufficientCredits):
        client.reserve(clerk_id="u1", email=None, tool="translate", task_id="t1")


def test_billing_client_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    client = _mock_billing_client(httpx.MockTransport(handler))
    with pytest.raises(BillingUnavailable):
        client.reserve(clerk_id="u1", email=None, tool="translate", task_id="t1")
