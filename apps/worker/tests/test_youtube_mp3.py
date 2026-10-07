"""Unit tests for the youtube2mp3 handler (no network, no binaries)."""

from __future__ import annotations

import pytest
from common.providers.base import ProviderUnavailable
from worker.handlers.base import HandlerContext
from worker.handlers.youtube_mp3 import extract_video_id, handle_youtube2mp3


class _Store:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_bytes(self, key: str) -> bytes:
        return self._data


def _ctx(url: bytes, params: dict | None = None) -> HandlerContext:
    return HandlerContext(
        task_id="t1",
        slug="youtube2mp3",
        object_store=_Store(url),
        input_key="in",
        params=params or {},
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ&list=abc", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id_ok(url: str, expected: str) -> None:
    assert extract_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/123",
        "https://www.youtube.com/watch",
        "not a url",
        "ftp://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_extract_video_id_rejects(url: str) -> None:
    with pytest.raises(ValueError):
        extract_video_id(url)


def test_rejects_bad_quality() -> None:
    ctx = _ctx(b"https://youtu.be/dQw4w9WgXcQ", {"quality": "999"})
    with pytest.raises(ValueError, match="Qualidade"):
        handle_youtube2mp3(ctx)


def test_rejects_non_youtube() -> None:
    ctx = _ctx(b"https://example.com/video")
    with pytest.raises(ValueError, match="YouTube"):
        handle_youtube2mp3(ctx)


def test_no_oracle_no_binaries_is_provider_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("MEDIA_URL", raising=False)
    import common.config as config_mod

    config_mod.get_settings.cache_clear()
    monkeypatch.setattr("shutil.which", lambda name: None)
    ctx = _ctx(b"https://youtu.be/dQw4w9WgXcQ")
    with pytest.raises(ProviderUnavailable):
        handle_youtube2mp3(ctx)
    config_mod.get_settings.cache_clear()


def test_via_oracle_ok(monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_URL", "http://oracle.local:8000")
    import common.config as config_mod

    config_mod.get_settings.cache_clear()

    class _Resp:
        status_code = 200
        content = b"ID3fake-mp3-bytes"

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    ctx = _ctx(b"https://youtu.be/dQw4w9WgXcQ", {"quality": "320"})
    result = handle_youtube2mp3(ctx)
    assert result.key.endswith("-320k.mp3")
    assert result.content_type == "audio/mpeg"
    assert result.data.startswith(b"ID3")
    config_mod.get_settings.cache_clear()
