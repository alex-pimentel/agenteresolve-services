"""Tests for remote/local capability providers and the OpenAI-compatible LLM.

Remote providers are exercised with a fake httpx client (no network). Local providers that
need heavy optional dependencies are asserted to raise ProviderUnavailable.
"""

from __future__ import annotations

from typing import Any

import pytest
from common.providers import capabilities as caps
from common.providers.base import ProviderUnavailable
from common.providers.llm import OpenAICompatibleLLM
from common.providers.local import (
    HashingEmbeddingsProvider,
    LocalAudioProvider,
    LocalOcrProvider,
    LocalTtsProvider,
    LocalVisionProvider,
)


class _Response:
    def __init__(self, payload: Any = None, content: bytes = b"") -> None:
        self._payload = payload
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class _Client:
    def __init__(self, response: _Response, **_: Any) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self._response

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self._response


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, response: _Response) -> _Client:
    client = _Client(response)
    monkeypatch.setattr("httpx.Client", lambda **kwargs: client)
    return client


def test_remote_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, _Response({"data": [{"embedding": [0.1, 0.2]}]}))
    provider = caps.RemoteEmbeddingsProvider("https://x", "k")
    assert provider.embed(["hi"]) == [[0.1, 0.2]]


def test_remote_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(
        monkeypatch,
        _Response({"blocks": [{"text": "hi", "bbox": [0, 0, 1, 1], "confidence": 0.9}]}),
    )
    blocks = caps.RemoteOcrProvider("https://x", "k").extract(b"d", content_type="image/png")
    assert blocks[0].text == "hi"


def test_remote_vision_caption_and_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, _Response({"caption": "a cat"}))
    assert caps.RemoteVisionProvider("https://x", "k").caption(b"d", content_type="image/png") == (
        "a cat"
    )
    _patch_httpx(
        monkeypatch,
        _Response({"detections": [{"label": "car", "bbox": [0, 0, 1, 1], "score": 0.7}]}),
    )
    detections = caps.RemoteVisionProvider("https://x", "k").detect(
        b"d", content_type="image/png", labels=["car"]
    )
    assert detections[0].label == "car"


def test_remote_audio_transcribe_and_enhance(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(
        monkeypatch,
        _Response(
            {
                "text": "hi",
                "segments": [{"start": 0.0, "end": 1.0, "text": "hi"}],
                "language": "en",
            }
        ),
    )
    transcription = caps.RemoteAudioProvider("https://x", "k").transcribe(
        b"d", content_type="audio/wav"
    )
    assert transcription.segments[0].text == "hi"

    _patch_httpx(monkeypatch, _Response(content=b"clean"))
    assert (
        caps.RemoteAudioProvider("https://x", "k").enhance(
            b"d", content_type="audio/wav", mode="denoise"
        )
        == b"clean"
    )


def test_remote_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, _Response(content=b"AUDIO"))
    assert caps.RemoteTtsProvider("https://x", "k").synthesize("hi") == b"AUDIO"


def test_openai_compatible_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, _Response({"choices": [{"message": {"content": "hello"}}]}))
    llm = OpenAICompatibleLLM("https://x/v1", "key", "model")
    assert llm.complete("prompt", system="sys", max_tokens=5) == "hello"


def test_local_providers_require_optional_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    import common.providers.local as local_mod

    def _missing(module: str) -> Any:
        raise ProviderUnavailable(f"Optional dependency '{module}' is not installed.")

    # Force the optional-dependency path regardless of what is installed in the env.
    monkeypatch.setattr(local_mod, "_require", _missing)
    for provider_call in (
        lambda: LocalOcrProvider().extract(b"x", content_type="image/png"),
        lambda: LocalVisionProvider().caption(b"x", content_type="image/png"),
        lambda: LocalAudioProvider().transcribe(b"x", content_type="audio/wav"),
        lambda: LocalTtsProvider().synthesize("hi"),
    ):
        with pytest.raises(ProviderUnavailable):
            provider_call()


def test_hashing_embeddings_are_deterministic_and_normalized() -> None:
    provider = HashingEmbeddingsProvider()
    first = provider.embed(["apple banana"])[0]
    second = provider.embed(["apple banana"])[0]
    assert first == second
    assert pytest.approx(sum(v * v for v in first) ** 0.5, rel=1e-6) == 1.0


def test_local_provider_flags() -> None:
    assert LocalOcrProvider().is_remote is False
    assert caps.LocalEmbeddingsProvider().is_remote is False
