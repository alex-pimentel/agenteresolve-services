import pytest
from common.providers import factory
from common.providers.base import ProviderUnavailable
from common.providers.llm import FakeLLM, OpenAICompatibleLLM


def test_fake_llm_returns_configured_response() -> None:
    assert FakeLLM("hello").complete("anything") == "hello"


def test_fake_llm_records_calls() -> None:
    llm = FakeLLM(lambda **kwargs: kwargs["prompt"].upper())
    assert llm.complete("hi", system="s") == "HI"
    assert llm.calls[0]["prompt"] == "hi"
    assert llm.calls[0]["system"] == "s"


def test_factory_uses_remote_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "m")
    factory.reset_providers()
    assert isinstance(factory.get_llm_provider(), OpenAICompatibleLLM)


def test_factory_uses_openrouter_default_when_only_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "secret")
    factory.reset_providers()
    provider = factory.get_llm_provider()
    assert isinstance(provider, OpenAICompatibleLLM)
    assert "openrouter.ai" in provider.base_url


def test_factory_raises_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    factory.reset_providers()
    with pytest.raises(ProviderUnavailable):
        factory.get_llm_provider().complete("x")


def test_llm_override_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    factory.set_llm_provider(FakeLLM("over"))
    assert factory.get_llm_provider().complete("x") == "over"
    factory.reset_providers()


def test_ocr_remote_vs_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_URL", "https://ocr.example.com")
    monkeypatch.setenv("OCR_KEY", "k")
    factory.reset_providers()
    remote = factory.get_ocr_provider()
    assert remote.is_remote is True

    monkeypatch.delenv("OCR_URL", raising=False)
    monkeypatch.delenv("OCR_KEY", raising=False)
    factory.reset_providers()
    local = factory.get_ocr_provider()
    assert local.is_remote is False
