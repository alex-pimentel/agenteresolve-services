"""Resolver tests: admin-backed LLM config with TTL cache and env fallback."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
import pytest

from common import llm_config


class _RecordingTransport(httpx.MockTransport):
    def __init__(
        self, handler: Callable[[httpx.Request], httpx.Response], calls: list[httpx.Request]
    ) -> None:
        super().__init__(handler)
        self.calls = calls


@pytest.fixture(autouse=True)
def _reset():
    llm_config.clear_llm_cache()
    yield
    llm_config.clear_llm_cache()


def _transport(payload: dict | None, *, status: int = 200) -> _RecordingTransport:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if payload is None:
            raise httpx.ConnectError("down")
        return httpx.Response(status, json=payload)

    return _RecordingTransport(handler, calls)


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    monkeypatch.setenv("BILLING_BASE_URL", "https://portal.test")
    monkeypatch.setenv("CREDITS_SERVICE_TOKEN", "svc-token")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(value))
    from common.config import get_settings

    get_settings.cache_clear()


def test_admin_hit_returns_admin_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch)
    transport = _transport(
        {
            "mode": "oracle",
            "base_url": "http://oracle.local:8000/v1",
            "model": "translategemma:4b",
            "api_key": "inf-key",
        }
    )
    result = llm_config.get_effective_llm("translate", transport=transport)
    assert result.source == "admin"
    assert result.base_url == "http://oracle.local:8000/v1"
    assert result.model == "translategemma:4b"
    assert result.api_key == "inf-key"
    assert transport.calls[0].headers["X-Service-Token"] == "svc-token"
    assert "tool=translate" in str(transport.calls[0].url)


def test_second_call_within_ttl_makes_no_new_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(monkeypatch)
    transport = _transport({"mode": "api", "base_url": "b", "model": "m", "api_key": None})
    llm_config.get_effective_llm(None, transport=transport)
    llm_config.get_effective_llm(None, transport=transport)
    assert len(transport.calls) == 1


def test_expired_ttl_refetches(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch)
    transport = _transport({"mode": "api", "base_url": "b", "model": "m", "api_key": None})
    llm_config.get_effective_llm(None, transport=transport)
    stale = llm_config.EffectiveLlm("b", None, "m", "admin")
    llm_config._CACHE["__all__"] = (time.monotonic() - 61.0, stale)
    llm_config.get_effective_llm(None, transport=transport)
    assert len(transport.calls) == 2


def test_unreachable_portal_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch)
    transport = _transport(None)
    result = llm_config.get_effective_llm("translate", transport=transport)
    assert result.source == "env"
    assert result.base_url == "https://openrouter.ai/api/v1"
    assert result.api_key == "env-key"
    assert result.model == "openai/gpt-4o-mini"


def test_invalid_payload_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch)
    transport = _transport({"mode": "api"}, status=200)
    result = llm_config.get_effective_llm(None, transport=transport)
    assert result.source == "env"


def test_missing_portal_config_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, BILLING_BASE_URL=None)
    transport = _transport({"mode": "api", "base_url": "b", "model": "m", "api_key": None})
    result = llm_config.get_effective_llm(None, transport=transport)
    assert result.source == "env"
    assert len(transport.calls) == 0
