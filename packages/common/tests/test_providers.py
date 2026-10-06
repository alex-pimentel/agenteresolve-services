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


def _admin_config() -> object:
    from common.llm_config import EffectiveLlm

    return EffectiveLlm(
        base_url="http://oracle.local:8000/v1",
        api_key="inf-key",
        model="translategemma:4b",
        source="admin",
    )


def test_factory_uses_admin_config_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setattr("common.llm_config.get_effective_llm", lambda tool=None: _admin_config())
    factory.reset_providers()
    provider = factory.get_llm_provider()
    assert isinstance(provider, OpenAICompatibleLLM)
    assert provider.base_url == "http://oracle.local:8000/v1"
    assert provider.model == "translategemma:4b"


def test_factory_tool_is_forwarded_to_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}
    from common.llm_config import EffectiveLlm

    def fake(tool: str | None = None) -> EffectiveLlm:
        seen["tool"] = tool
        return EffectiveLlm(base_url="", api_key=None, model="m", source="env")

    monkeypatch.setattr("common.llm_config.get_effective_llm", fake)
    factory.reset_providers()
    factory.get_llm_provider(tool="translate")
    assert seen["tool"] == "translate"


def test_explicit_model_keeps_env_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setattr("common.llm_config.get_effective_llm", lambda tool=None: _admin_config())
    factory.reset_providers()
    provider = factory.get_llm_provider_for_model("custom-model")
    assert isinstance(provider, OpenAICompatibleLLM)
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.model == "custom-model"


class _FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "Olá"}}]}


def _capture_client(captured: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, json: object = None, headers: dict | None = None) -> _FakeResponse:
            captured.update(headers or {})
            return _FakeResponse()

    monkeypatch.setattr("common.providers.llm.httpx.Client", _FakeClient)


def test_empty_key_omits_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _capture_client(captured, monkeypatch)
    llm = OpenAICompatibleLLM("https://example.com/v1", "", "m")
    assert llm.complete("hi") == "Olá"
    assert "Authorization" not in captured


def test_key_present_sends_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _capture_client(captured, monkeypatch)
    llm = OpenAICompatibleLLM("https://example.com/v1", "secret", "m")
    assert llm.complete("hi") == "Olá"
    assert captured["Authorization"] == "Bearer secret"


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
