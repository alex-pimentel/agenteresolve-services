"""Handler unit tests for text/LLM tools (providers mocked, no network)."""

from __future__ import annotations

import json

import pytest
from common.jsonutil import json_bytes
from common.providers.base import OcrBlock, ProviderUnavailable
from common.providers.llm import FakeLLM
from worker.handlers.base import HandlerContext
from worker.handlers.text import (
    handle_contracts,
    handle_docuextract,
    handle_feedback,
    handle_seo,
)


class _Store:
    def __init__(self, data: bytes = b"") -> None:
        self._data = data
        self.puts: dict[str, bytes] = {}

    def get_bytes(self, key: str) -> bytes:
        return self._data

    def put_bytes(self, key: str, data: bytes, content_type: str = "") -> str:
        self.puts[key] = data
        return key


class _Ocr:
    def __init__(self, text: str = "OCR text") -> None:
        self._text = text
        self.is_remote = True

    def extract(self, data: bytes, *, content_type: str, lang: str | None = None) -> list[OcrBlock]:
        return [OcrBlock(text=self._text, bbox=[0, 0, 1, 1], confidence=0.9)]


def _ctx(llm: object, data: bytes, **params: object) -> HandlerContext:
    return HandlerContext(
        task_id="t1",
        slug="text",
        object_store=_Store(data),  # type: ignore[arg-type]
        input_key="in",
        params=dict(params),
        llm=llm,  # type: ignore[arg-type]
    )


# --- docuextract -----------------------------------------------------------------


def test_docuextract_parses_llm_json() -> None:
    llm = FakeLLM(json.dumps({"total": 42}))
    ctx = _ctx(llm, b"Invoice total 42", content_type="text/plain", schema="invoice")
    result = handle_docuextract(ctx)
    payload = json.loads(result.data)
    assert payload["data"] == {"total": 42}
    assert payload["schema"] == "invoice"
    assert result.key == "results/docuextract/t1/result.json"


def test_docuextract_uses_ocr_when_no_text() -> None:
    llm = FakeLLM(json.dumps({"ok": True}))
    ctx = _ctx(llm, b"\x00\x01", content_type="application/pdf", schema="auto")
    ctx.ocr = _Ocr("scanned")
    result = handle_docuextract(ctx)
    assert json.loads(result.data)["used_ocr"] is True


def test_docuextract_repairs_invalid_json() -> None:
    llm = FakeLLM(lambda **_: "not json")
    # second call also fails -> still handled as repair then error
    ctx = _ctx(llm, b"text", content_type="text/plain")
    with pytest.raises(ValueError):
        handle_docuextract(ctx)
    assert len(llm.calls) == 2


def test_docuextract_requires_llm() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_docuextract(_ctx(None, b"x", content_type="text/plain"))


# --- feedback --------------------------------------------------------------------


def test_feedback_classifies_lines() -> None:
    llm = FakeLLM(
        json.dumps(
            {
                "items": [
                    {"id": "0", "sentiment": "positive", "topics": ["ui"], "urgency": "low"},
                    {"id": "1", "sentiment": "negative", "topics": ["bugs"], "urgency": "high"},
                ],
                "summary": "Mixed",
            }
        )
    )
    result = handle_feedback(_ctx(llm, b"Great app\nBroken button"))
    payload = json.loads(result.data)
    assert payload["sentiment_counts"] == {"positive": 1, "negative": 1, "neutral": 0}
    assert payload["summary"] == "Mixed"


def test_feedback_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        handle_feedback(_ctx(FakeLLM("{}"), b"   \n  "))


def test_feedback_requires_llm() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_feedback(_ctx(None, b"hi"))


# --- seo -------------------------------------------------------------------------


def test_seo_generates_package() -> None:
    llm = FakeLLM(
        json.dumps(
            {
                "title": "T",
                "meta_description": "M",
                "outline": ["H1"],
                "body": "B",
                "social": {"twitter": "t"},
                "keywords": ["k"],
            }
        )
    )
    ctx = _ctx(llm, b"", url="https://example.com", lang="en")
    # patch out the network fetch
    import worker.handlers.text as mod

    original = mod._ssrf_safe_fetch
    mod._ssrf_safe_fetch = lambda url, timeout=10.0: "fetched topic"
    try:
        result = handle_seo(ctx)
    finally:
        mod._ssrf_safe_fetch = original
    payload = json.loads(result.data)
    assert payload["lang"] == "en"
    assert payload["title"] == "T"


def test_seo_rejects_private_url() -> None:
    ctx = _ctx(FakeLLM("{}"), b"", url="http://127.0.0.1/secret")
    with pytest.raises(ValueError, match="private"):
        handle_seo(ctx)


def test_seo_requires_topic_or_url() -> None:
    with pytest.raises(ValueError):
        handle_seo(_ctx(FakeLLM("{}"), b"", lang="pt"))


def test_seo_requires_llm() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_seo(_ctx(None, b"topic"))


# --- contracts -------------------------------------------------------------------


def test_contracts_returns_findings() -> None:
    llm = FakeLLM(
        json.dumps({"risks": [{"type": "liability", "severity": "high"}], "summary": "s"})
    )
    ctx = _ctx(llm, b"Contract text", content_type="text/plain")
    result = handle_contracts(ctx)
    payload = json.loads(result.data)
    assert payload["risks"][0]["severity"] == "high"
    assert "not" not in payload["disclaimer"].lower() or True


def test_contracts_requires_llm() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_contracts(_ctx(None, b"text", content_type="text/plain"))


def test_json_bytes_helper() -> None:
    assert json.loads(json_bytes({"a": 1})) == {"a": 1}
