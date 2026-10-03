import pytest
from common.providers.base import ProviderUnavailable
from common.providers.llm import FakeLLM
from worker.handlers.base import HandlerContext, HandlerResult
from worker.handlers.translate import UnsupportedLanguage, handle_translate


class _Store:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_bytes(self, key: str) -> bytes:
        return self._data


def _ctx(
    llm: object,
    text: bytes = b"Hello",
    target: str = "pt",
    tone: str | None = None,
) -> HandlerContext:
    params: dict[str, str] = {"target": target}
    if tone is not None:
        params["tone"] = tone
    return HandlerContext(
        task_id="t1",
        slug="translate",
        object_store=_Store(text),  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
        input_key="in",
        params=params,
    )


def test_translate_returns_llm_output_and_key() -> None:
    result = handle_translate(_ctx(FakeLLM("Olá, mundo!")))
    assert isinstance(result, HandlerResult)
    assert result.data.decode() == "Olá, mundo!"
    assert result.key == "results/translate/t1/result.txt"
    assert "text/plain" in result.content_type


def test_translate_prompt_includes_target_tone_and_text() -> None:
    llm = FakeLLM("ok")
    handle_translate(_ctx(llm, text=b"Hello", target="es", tone="formal"))
    call = llm.calls[0]
    assert "es" in call["prompt"]
    assert "formal" in call["prompt"]
    assert "Hello" in call["prompt"]
    assert call["system"] is not None


def test_translate_rejects_unsupported_language() -> None:
    with pytest.raises(UnsupportedLanguage):
        handle_translate(_ctx(FakeLLM("x"), target="klingon"))


def test_translate_requires_llm() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_translate(_ctx(None))
