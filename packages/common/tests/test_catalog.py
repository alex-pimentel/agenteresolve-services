import pytest
from common.catalog import CATALOG, SLUGS, get_tool

from common import catalog

EXPECTED = {
    "louder",
    "qrcode",
    "imposition",
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


def test_catalog_has_eighteen_slugs() -> None:
    assert set(SLUGS) == EXPECTED
    assert len(SLUGS) == 18


def test_module_docstring_agrees_with_the_real_slug_count() -> None:
    """O docstring declara o catálogo canônico; se ele mentir, alguém vai confiar nele."""
    assert f"{len(SLUGS)} slugs" in (catalog.__doc__ or "")


def test_every_gateway_tool_is_implemented() -> None:
    implemented = {slug for slug, spec in CATALOG.items() if spec.implemented}
    assert implemented == EXPECTED - {"louder", "qrcode", "imposition"}
    assert CATALOG["louder"].implemented is False
    assert CATALOG["qrcode"].implemented is False
    assert CATALOG["imposition"].implemented is False


def test_tool_metadata_fields() -> None:
    assert get_tool("translate").input_kind == "text"
    assert get_tool("translate").result_kind == "text"
    assert get_tool("ocr").input_kind == "image"
    assert get_tool("ocr").result_kind == "json"
    assert get_tool("anonymize").result_kind == "image"
    assert get_tool("tts").input_kind == "text"
    assert get_tool("tts").result_kind == "audio"


def test_queue_assignment_by_category() -> None:
    assert get_tool("translate").queue == "text"
    assert get_tool("ocr").queue == "vision"
    assert get_tool("tts").queue == "audio"
    assert get_tool("louder").queue is None


def test_unknown_tool_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_tool("does-not-exist")
