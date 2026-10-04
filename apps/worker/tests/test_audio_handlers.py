"""Handler unit tests for audio tools (providers mocked, no network)."""

from __future__ import annotations

import json

import pytest
from common.providers.base import ProviderUnavailable, Transcription, TranscriptSegment
from common.providers.llm import FakeLLM
from worker.handlers.audio import handle_audio_enhance, handle_transcribe, handle_tts
from worker.handlers.base import HandlerContext


class _Store:
    def __init__(self, data: bytes = b"") -> None:
        self._data = data

    def get_bytes(self, key: str) -> bytes:
        return self._data


class _Audio:
    is_remote = True

    def transcribe(
        self, data: bytes, *, content_type: str, lang: str | None = None
    ) -> Transcription:
        return Transcription(
            text="hello world",
            segments=[
                TranscriptSegment(start=0.0, end=1.5, text="hello"),
                TranscriptSegment(start=1.5, end=3.0, text="world"),
            ],
            language=lang or "en",
        )

    def enhance(self, data: bytes, *, content_type: str, mode: str = "denoise") -> bytes:
        return b"enhanced-" + mode.encode()


class _Tts:
    is_remote = True

    def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        lang: str | None = None,
        speed: float = 1.0,
    ) -> bytes:
        return b"AUDIO:" + text.encode()


def _ctx(**overrides: object) -> HandlerContext:
    base: dict[str, object] = {
        "task_id": "t1",
        "slug": "audio",
        "object_store": _Store(b"audio"),
        "input_key": "in",
        "params": {},
    }
    base.update(overrides)
    return HandlerContext(**base)  # type: ignore[arg-type]


# --- transcribe ------------------------------------------------------------------


def test_transcribe_returns_segments_and_srt() -> None:
    ctx = _ctx(audio=_Audio(), params={"lang": "auto"})
    payload = json.loads(handle_transcribe(ctx).data)
    assert payload["language"] == "en"
    assert payload["segments"][0]["text"] == "hello"
    assert "00:00:00,000 --> 00:00:01,500" in payload["srt"]
    assert payload["summary"] is None


def test_transcribe_with_summary() -> None:
    llm = FakeLLM(json.dumps({"summary": "s", "topics": ["t"], "action_items": []}))
    ctx = _ctx(audio=_Audio(), llm=llm, params={"summarize": "true"})
    payload = json.loads(handle_transcribe(ctx).data)
    assert payload["summary"]["summary"] == "s"


def test_transcribe_requires_audio() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_transcribe(_ctx())


# --- tts -------------------------------------------------------------------------


def test_tts_synthesizes_audio() -> None:
    ctx = _ctx(tts=_Tts(), params={"text": "hi"})
    ctx.object_store._data = b"Hello"  # type: ignore[attr-defined]
    result = handle_tts(ctx)
    assert result.data == b"AUDIO:Hello"
    assert result.key == "results/tts/t1/result.mp3"
    assert result.content_type == "audio/mpeg"


def test_tts_requires_provider() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_tts(_ctx())


def test_tts_rejects_empty_text() -> None:
    ctx = _ctx(tts=_Tts(), object_store=_Store(b"   "))
    with pytest.raises(ValueError):
        handle_tts(ctx)


# --- audio-enhance ---------------------------------------------------------------


def test_audio_enhance_returns_wav() -> None:
    ctx = _ctx(audio=_Audio(), params={"mode": "voice-isolate"})
    result = handle_audio_enhance(ctx)
    assert result.data == b"enhanced-voice-isolate"
    assert result.key == "results/audio-enhance/t1/result.wav"


def test_audio_enhance_rejects_bad_mode() -> None:
    with pytest.raises(ValueError):
        handle_audio_enhance(_ctx(audio=_Audio(), params={"mode": "turbo"}))


def test_audio_enhance_requires_audio() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_audio_enhance(_ctx())
