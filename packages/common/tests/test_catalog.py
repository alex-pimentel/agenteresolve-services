import pytest
from common.catalog import CATALOG, SLUGS, get_tool

EXPECTED = {
    "louder",
    "docuextract",
    "askyourdocs",
    "datachat",
    "feedback",
    "seo",
    "translate",
    "contracts",
    "ocr",
    "anonymize",
    "alttext",
    "objectcount",
    "transcribe",
    "tts",
    "audio-enhance",
    "voicechat",
}


def test_catalog_has_sixteen_slugs() -> None:
    assert set(SLUGS) == EXPECTED
    assert len(SLUGS) == 16


def test_only_translate_is_implemented() -> None:
    implemented = {slug for slug, spec in CATALOG.items() if spec.implemented}
    assert implemented == {"translate"}


def test_queue_assignment_by_category() -> None:
    assert get_tool("translate").queue == "text"
    assert get_tool("ocr").queue == "vision"
    assert get_tool("tts").queue == "audio"
    assert get_tool("louder").queue is None


def test_unknown_tool_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_tool("does-not-exist")
