"""Client for the centralized billing API (Laravel, source of truth).

The gateway reserves credits synchronously on job creation and settles
afterwards: ``commit`` on success, ``refund`` on any failure — so failed
calls are never charged. Per-tool settlement must never happen in workers
or backends; the gateway is the single choke-point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from common.config import get_settings

if TYPE_CHECKING:
    import httpx


class BillingError(RuntimeError):
    """Base class for billing failures."""


class InsufficientCredits(BillingError):
    def __init__(self, balance: int, required: int) -> None:
        super().__init__(f"Insufficient credits: balance {balance}, required {required}.")
        self.balance = balance
        self.required = required


class BillingUnavailable(BillingError):
    """The billing API could not be reached or returned an unexpected error."""


@dataclass
class Reservation:
    task_id: str
    cost: int
    balance: int


class BillingClient:
    """Thin wrapper over the Laravel internal billing endpoints."""

    def __init__(
        self,
        base_url: str,
        service_token: str,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        import httpx

        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-Service-Token": service_token},
            timeout=timeout,
            transport=transport,
        )

    def enabled(self) -> bool:
        return True

    def reserve(
        self,
        *,
        clerk_id: str,
        email: str | None,
        tool: str,
        task_id: str,
        idempotency_key: str | None = None,
    ) -> Reservation:
        import httpx

        payload: dict[str, object] = {
            "clerk_id": clerk_id,
            "tool": tool,
            "task_id": task_id,
        }
        if email:
            payload["email"] = email
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        try:
            response = self._http.post("/api/internal/credits/reserve", json=payload)
        except httpx.HTTPError as exc:
            raise BillingUnavailable(f"Billing reserve failed: {exc}") from exc
        if response.status_code == 402:
            try:
                body = response.json()
            except ValueError:
                body = {}
            raise InsufficientCredits(
                balance=int(body.get("balance", 0)),
                required=int(body.get("required", 0)),
            )
        if response.status_code not in (200, 201):
            raise BillingUnavailable(f"Billing reserve failed: HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise BillingUnavailable("Billing reserve returned invalid JSON") from exc
        return Reservation(
            task_id=str(body.get("task_id", task_id)),
            cost=int(body.get("cost", 0)),
            balance=int(body.get("balance", 0)),
        )

    def commit(self, *, task_id: str, status_code: int = 200, latency_ms: int | None = None) -> int:
        """Settle a successful call. Returns the charged cost. Idempotent."""
        import httpx

        payload: dict[str, object] = {"task_id": task_id, "status_code": status_code}
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
        try:
            response = self._http.post("/api/internal/credits/commit", json=payload)
        except httpx.HTTPError as exc:
            raise BillingUnavailable(f"Billing commit failed: {exc}") from exc
        if response.status_code == 404:
            return 0
        if response.status_code != 200:
            raise BillingUnavailable(f"Billing commit failed: HTTP {response.status_code}")
        try:
            return int(response.json().get("cost", 0))
        except ValueError as exc:
            raise BillingUnavailable("Billing commit returned invalid JSON") from exc

    def refund(self, *, task_id: str, reason: str = "failed") -> None:
        """Refund a failed call. Never raises for unknown tasks."""
        import httpx

        try:
            response = self._http.post(
                "/api/internal/credits/refund", json={"task_id": task_id, "reason": reason}
            )
        except httpx.HTTPError as exc:
            raise BillingUnavailable(f"Billing refund failed: {exc}") from exc
        if response.status_code in (200, 201, 404):
            return
        raise BillingUnavailable(f"Billing refund failed: HTTP {response.status_code}")

    def balance(self, *, clerk_id: str) -> int:
        """Current credit balance. Returns 0 when the user is unknown."""
        import httpx

        try:
            response = self._http.get(
                "/api/internal/credits/balance", params={"clerk_id": clerk_id}
            )
        except httpx.HTTPError as exc:
            raise BillingUnavailable(f"Billing balance failed: {exc}") from exc
        if response.status_code == 404:
            return 0
        if response.status_code != 200:
            raise BillingUnavailable(f"Billing balance failed: HTTP {response.status_code}")
        try:
            return int(response.json().get("balance", 0))
        except ValueError as exc:
            raise BillingUnavailable("Billing balance returned invalid JSON") from exc


class DisabledBillingClient:
    """No-op billing used when BILLING_ENABLED=false (dev/tests)."""

    def enabled(self) -> bool:
        return False

    def reserve(self, **kwargs: object) -> Reservation:
        return Reservation(task_id=str(kwargs.get("task_id", "")), cost=0, balance=0)

    def commit(self, **kwargs: object) -> int:
        return 0

    def refund(self, **kwargs: object) -> None:
        return None

    def balance(self, **kwargs: object) -> int:
        return 0


def build_billing_client() -> BillingClient | DisabledBillingClient:
    settings = get_settings()
    if settings.billing_enabled and settings.billing_base_url and settings.billing_service_token:
        return BillingClient(
            base_url=settings.billing_base_url,
            service_token=settings.billing_service_token,
            timeout=settings.billing_timeout,
        )
    return DisabledBillingClient()


_billing_client: BillingClient | DisabledBillingClient | None = None


def get_billing_client() -> BillingClient | DisabledBillingClient:
    global _billing_client
    if _billing_client is None:
        _billing_client = build_billing_client()
    return _billing_client


def set_billing_client(client: BillingClient | DisabledBillingClient | None) -> None:
    global _billing_client
    _billing_client = client


def reset_billing_client() -> None:
    set_billing_client(None)
