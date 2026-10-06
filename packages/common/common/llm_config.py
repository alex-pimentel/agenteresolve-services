"""Effective LLM config: admin (Laravel) wins, env is the fallback.

Workers call :func:`get_effective_llm` instead of reading ``LLM_*`` env vars
directly. The admin answer is cached in memory for ``CACHE_TTL_SECONDS`` so a
change in the Filament panel takes effect within a minute with no restart; any
failure (unreachable portal, timeout, bad payload) falls back to the env-derived
config and only logs a warning, so the workers never break because of this.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60.0
FETCH_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class EffectiveLlm:
    base_url: str
    api_key: str | None
    model: str
    source: Literal["admin", "env"]


_CACHE: dict[str, tuple[float, EffectiveLlm]] = {}


def clear_llm_cache() -> None:
    _CACHE.clear()


def _cache_key(tool: str | None) -> str:
    return tool if tool else "__all__"


def _env_config() -> EffectiveLlm:
    from common.config import get_settings

    settings = get_settings()
    base_url = settings.llm_base_url
    if not base_url and settings.llm_api_key:
        base_url = "https://openrouter.ai/api/v1"
    return EffectiveLlm(
        base_url=base_url or "",
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        source="env",
    )


def _fetch_admin(tool: str | None, transport: Any = None) -> EffectiveLlm | None:
    import httpx

    from common.config import get_settings

    settings = get_settings()
    portal = (settings.billing_base_url or "").rstrip("/")
    token = settings.billing_service_token
    if not portal or not token:
        return None
    params = {"tool": tool} if tool else {}
    try:
        with httpx.Client(
            base_url=portal,
            headers={"X-Service-Token": token},
            timeout=FETCH_TIMEOUT_SECONDS,
            transport=transport,
        ) as client:
            response = client.get("/api/internal/llm-config", params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - any fetch problem means env fallback
        logger.warning("llm-config fetch failed, using env fallback: %s", exc)
        return None
    if not isinstance(data, dict):
        logger.warning("llm-config invalid payload, using env fallback")
        return None
    try:
        base_url = str(data["base_url"])
        model = str(data["model"])
    except (KeyError, TypeError, ValueError):
        logger.warning("llm-config missing fields, using env fallback")
        return None
    api_key = data.get("api_key")
    return EffectiveLlm(
        base_url=base_url,
        api_key=str(api_key) if api_key else None,
        model=model,
        source="admin",
    )


def get_effective_llm(tool: str | None = None, transport: Any = None) -> EffectiveLlm:
    key = _cache_key(tool)
    cached = _CACHE.get(key)
    if cached is not None:
        stored_at, config = cached
        if time.monotonic() - stored_at < CACHE_TTL_SECONDS:
            return config
    admin = _fetch_admin(tool, transport=transport)
    if admin is not None and not admin.api_key:
        logger.info("llm-config has no key yet, using env fallback")
        admin = None
    config = admin if admin is not None else _env_config()
    _CACHE[key] = (time.monotonic(), config)
    return config
