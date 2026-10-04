"""Provider factory driven entirely by environment variables.

Rule for every capability except the LLM: if ``*_URL`` is set, use the remote HTTP
endpoint; otherwise use the local backend. The LLM defaults to OpenRouter when only
``LLM_API_KEY`` is set (OpenAI-compatible).
"""

from __future__ import annotations

from typing import Any

from common.config import get_settings
from common.providers import capabilities as caps
from common.providers.base import (
    AudioProvider,
    EmbeddingsProvider,
    LLMProvider,
    OcrProvider,
    TtsProvider,
    VisionProvider,
)
from common.providers.llm import OPENROUTER_BASE_URL, LocalLLM, OpenAICompatibleLLM

_llm_override: LLMProvider | None = None
_overrides: dict[str, Any] = {}


def set_llm_provider(provider: LLMProvider | None) -> None:
    """Override the LLM provider (used by tests and local wiring)."""
    global _llm_override
    _llm_override = provider


def set_provider(capability: str, provider: Any | None) -> None:
    """Override any capability provider (used by tests and local wiring)."""
    if provider is None:
        _overrides.pop(capability, None)
    else:
        _overrides[capability] = provider


def reset_providers() -> None:
    global _llm_override
    _llm_override = None
    _overrides.clear()
    get_settings.cache_clear()


def get_llm_provider() -> LLMProvider:
    if _llm_override is not None:
        return _llm_override
    settings = get_settings()
    base_url = settings.llm_base_url
    if not base_url and settings.llm_api_key:
        base_url = OPENROUTER_BASE_URL
    if base_url:
        return OpenAICompatibleLLM(
            base_url=base_url,
            api_key=settings.llm_api_key or "",
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )
    return LocalLLM(settings.llm_model)


def get_embeddings_provider() -> EmbeddingsProvider:
    if "embeddings" in _overrides:
        return _overrides["embeddings"]
    settings = get_settings()
    if settings.embeddings_base_url:
        return caps.RemoteEmbeddingsProvider(
            settings.embeddings_base_url, settings.embeddings_api_key, settings.embeddings_model
        )
    return caps.LocalEmbeddingsProvider(model=settings.embeddings_model)


def get_ocr_provider() -> OcrProvider:
    if "ocr" in _overrides:
        return _overrides["ocr"]
    settings = get_settings()
    return _select(
        settings.ocr_url,
        settings.ocr_key,
        caps.RemoteOcrProvider,
        caps.LocalOcrProvider,
    )


def get_vision_provider() -> VisionProvider:
    if "vision" in _overrides:
        return _overrides["vision"]
    settings = get_settings()
    return _select(
        settings.vision_url,
        settings.vision_key,
        caps.RemoteVisionProvider,
        caps.LocalVisionProvider,
    )


def get_audio_provider() -> AudioProvider:
    if "audio" in _overrides:
        return _overrides["audio"]
    settings = get_settings()
    return _select(
        settings.audio_url,
        settings.audio_key,
        caps.RemoteAudioProvider,
        caps.LocalAudioProvider,
    )


def get_tts_provider() -> TtsProvider:
    if "tts" in _overrides:
        return _overrides["tts"]
    settings = get_settings()
    return _select(
        settings.tts_url,
        settings.tts_key,
        caps.RemoteTtsProvider,
        caps.LocalTtsProvider,
    )


def _select(
    url: str | None,
    key: str | None,
    remote_cls: type[Any],
    local_cls: type[Any],
) -> Any:
    if url:
        return remote_cls(url, key)
    return local_cls()
