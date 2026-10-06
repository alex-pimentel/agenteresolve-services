"""LLM providers.

``OpenAICompatibleLLM`` talks to any OpenAI-compatible ``/chat/completions`` endpoint
(OpenRouter by default, but also OpenAI, Groq or a local Ollama). ``LocalLLM`` is the
placeholder for a self-hosted backend; ``FakeLLM`` is used in tests.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from common.providers.base import ProviderUnavailable

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenAICompatibleLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        content: str = data["choices"][0]["message"]["content"] or ""
        return content


class LocalLLM:
    """Placeholder for a self-hosted LLM. Configure ``LLM_BASE_URL`` to use a server."""

    is_remote = False

    def __init__(self, model: str | None = None, **_: Any) -> None:
        self.model = model

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        raise ProviderUnavailable(
            "No LLM backend configured. Set LLM_BASE_URL and LLM_API_KEY "
            "(default provider: OpenRouter) or run a local OpenAI-compatible server."
        )


class FakeLLM:
    """Deterministic in-process LLM used by tests (no network)."""

    def __init__(self, responder: str | Callable[..., str] = "") -> None:
        self.responder = responder
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if callable(self.responder):
            return self.responder(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return self.responder
