"""Handler unit tests for vision tools (providers mocked, no network)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from common.providers.base import Detection, ProviderUnavailable
from common.providers.llm import FakeLLM
from worker.handlers.base import HandlerContext
from worker.handlers.vision import (
    _blur_regions,
    handle_alttext,
    handle_anonymize,
    handle_objectcount,
    handle_ocr,
    non_max_suppression,
)


class _Store:
    def __init__(self, data: bytes = b"") -> None:
        self._data = data

    def get_bytes(self, key: str) -> bytes:
        return self._data


class _Ocr:
    is_remote = True

    def extract(self, data: bytes, *, content_type: str, lang: str | None = None):
        from common.providers.base import OcrBlock

        return [
            OcrBlock(text="hello", bbox=[0, 0, 10, 10], confidence=0.99),
            OcrBlock(text="world", bbox=[10, 0, 20, 10], confidence=0.8),
        ]


class _Vision:
    is_remote = True

    def __init__(
        self, caption_text: str = "a cat", detections: list[Detection] | None = None
    ) -> None:
        self._caption = caption_text
        self._detections = detections or []

    def caption(self, data: bytes, *, content_type: str) -> str:
        return self._caption

    def detect(
        self, data: bytes, *, content_type: str, labels: list[str] | None = None
    ) -> list[Detection]:
        if labels:
            return [d for d in self._detections if d.label in labels]
        return self._detections


def _ctx(**overrides: object) -> HandlerContext:
    base: dict[str, object] = {
        "task_id": "t1",
        "slug": "vision",
        "object_store": _Store(b"img"),
        "input_key": "in",
        "params": {},
    }
    base.update(overrides)
    return HandlerContext(**base)  # type: ignore[arg-type]


# --- ocr -------------------------------------------------------------------------


def test_ocr_returns_text_and_blocks() -> None:
    ctx = _ctx(ocr=_Ocr(), params={"lang": "eng"})
    result = handle_ocr(ctx)
    payload = json.loads(result.data)
    assert payload["text"] == "hello\nworld"
    assert len(payload["blocks"]) == 2
    assert result.key == "results/ocr/t1/result.json"


def test_ocr_requires_provider() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_ocr(_ctx())


# --- alttext ---------------------------------------------------------------------


def test_alttext_refines_with_llm() -> None:
    llm = FakeLLM(json.dumps({"alt": "Um gato", "caption": ["gato"], "tags": ["cat"]}))
    ctx = _ctx(vision=_Vision("a cat"), llm=llm, params={"lang": "pt", "style": "accessible"})
    result = handle_alttext(ctx)
    payload = json.loads(result.data)
    assert payload["alt"] == "Um gato"
    assert payload["tags"] == ["cat"]


def test_alttext_without_llm_uses_caption() -> None:
    ctx = _ctx(vision=_Vision("a dog"))
    payload = json.loads(handle_alttext(ctx).data)
    assert payload["alt"] == "a dog"


def test_alttext_falls_back_to_caption_when_llm_is_unavailable() -> None:
    def unavailable(**_: Any) -> str:
        raise ProviderUnavailable("LLM offline")

    ctx = _ctx(
        vision=_Vision("a cat"),
        llm=FakeLLM(unavailable),
        params={"lang": "pt", "style": "accessible"},
    )
    payload = json.loads(handle_alttext(ctx).data)
    assert payload["alt"] == "a cat"
    assert payload["caption"] == ["a cat"]
    assert payload["tags"] == []


def test_alttext_requires_vision() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_alttext(_ctx(llm=FakeLLM("x")))


# --- objectcount -----------------------------------------------------------------


def test_objectcount_aggregates_by_class() -> None:
    detections = [
        Detection("person", [0, 0, 10, 10], 0.9),
        Detection("person", [1, 1, 11, 11], 0.95),
        Detection("car", [20, 20, 40, 40], 0.8),
    ]
    ctx = _ctx(vision=_Vision(detections=detections))
    payload = json.loads(handle_objectcount(ctx).data)
    assert payload["counts"] == {"person": 1, "car": 1}
    assert payload["total"] == 2


def test_objectcount_respects_min_score() -> None:
    detections = [Detection("person", [0, 0, 10, 10], 0.3)]
    ctx = _ctx(vision=_Vision(detections=detections), params={"min_score": 0.5})
    assert json.loads(handle_objectcount(ctx).data)["total"] == 0


def test_nms_suppresses_overlaps() -> None:
    detections = [
        Detection("person", [0, 0, 10, 10], 0.9),
        Detection("person", [1, 1, 11, 11], 0.5),
    ]
    assert len(non_max_suppression(detections)) == 1


def test_objectcount_requires_vision() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_objectcount(_ctx())


# --- anonymize -------------------------------------------------------------------


def test_anonymize_requires_vision() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_anonymize(_ctx())


def test_anonymize_blur_requires_pillow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(vision=_Vision(detections=[Detection("face", [0, 0, 5, 5], 0.9)]))
    import worker.handlers.vision as mod

    def _raise(*_: object, **__: object) -> bytes:
        raise ProviderUnavailable("no Pillow")

    monkeypatch.setattr(mod, "_blur_regions", _raise)
    with pytest.raises(ProviderUnavailable):
        handle_anonymize(ctx)


# --- _blur_regions ---------------------------------------------------------------


def _pattern_png(size: int = 40) -> bytes:
    """PNG com gradiente: garante que pixelate/blur mudem de fato a região."""
    import io

    from PIL import Image

    image = Image.new("RGB", (size, size))
    for x in range(size):
        for y in range(size):
            image.putpixel((x, y), (x * 6 % 256, y * 6 % 256, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _decode(data: bytes) -> Any:
    import io

    from PIL import Image

    return Image.open(io.BytesIO(data)).convert("RGB")


def test_blur_regions_applies_each_mode_only_to_the_target_box() -> None:
    box = [10.0, 10.0, 30.0, 30.0]
    original = _decode(_pattern_png())

    for mode in ("blur", "black", "pixelate"):
        redacted = _decode(_blur_regions(_pattern_png(), [box], mode))

        assert redacted.size == original.size
        assert redacted.crop(tuple(box)).tobytes() != original.crop(tuple(box)).tobytes(), mode
        assert redacted.crop((0, 0, 10, 40)).tobytes() == original.crop((0, 0, 10, 40)).tobytes(), (
            mode
        )
        if mode == "black":
            assert redacted.getpixel((20, 20)) == (0, 0, 0)


def test_blur_regions_ignores_degenerate_and_incomplete_boxes() -> None:
    original = _decode(_pattern_png())
    redacted = _decode(
        _blur_regions(_pattern_png(), [[10.0, 10.0, 10.0, 30.0], [5.0, 5.0]], "black")
    )

    assert redacted.tobytes() == original.tobytes()
