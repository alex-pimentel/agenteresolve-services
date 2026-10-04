"""Canonical tool catalogue: the single source of truth for the 16 slugs.

The gateway uses this registry to route requests and expose tool metadata (queue, input
kind, result kind, size limits) and to reject the one client-side tool. The worker uses the
queue field for routing. Every gateway tool is implemented; unavailable local models are
reported at runtime as ``503 provider_unavailable`` rather than at registration time.
"""

from dataclasses import dataclass
from typing import Literal

Category = Literal["client", "text", "vision", "audio"]
Queue = Literal["text", "vision", "audio"]
InputKind = Literal["text", "file", "image", "audio"]
ResultKind = Literal["text", "json", "download", "audio", "image"]

_KB = 1024
_MB = 1024 * 1024

QUEUES: tuple[str, ...] = ("text", "vision", "audio")


@dataclass(frozen=True)
class ToolSpec:
    slug: str
    name: str
    category: Category
    queue: Queue | None
    max_bytes: int
    input_kind: InputKind = "file"
    result_kind: ResultKind = "json"
    implemented: bool = True
    notes: str = ""


_TOOLS: tuple[ToolSpec, ...] = (
    # Client-side (browser, Cloudflare Pages) --------------------------------
    ToolSpec(
        "louder",
        "Louder",
        "client",
        None,
        25 * _MB,
        input_kind="file",
        result_kind="audio",
        implemented=False,
        notes="client-side only; no gateway endpoint",
    ),
    # Text / LLM --------------------------------------------------------------
    ToolSpec("docuextract", "DocuExtract", "text", "text", 20 * _MB, input_kind="file"),
    ToolSpec("askyourdocs", "AskYourDocs", "text", "text", 20 * _MB, input_kind="file"),
    ToolSpec("datachat", "DataChat", "text", "text", 20 * _MB, input_kind="file"),
    ToolSpec(
        "feedback",
        "FeedbackClassifier",
        "text",
        "text",
        200 * _KB,
        input_kind="text",
        result_kind="json",
    ),
    ToolSpec("seo", "SEOContent", "text", "text", 200 * _KB, input_kind="text", result_kind="json"),
    ToolSpec(
        "translate",
        "Translator",
        "text",
        "text",
        10 * _MB,
        input_kind="text",
        result_kind="text",
    ),
    ToolSpec("contracts", "ContractChecker", "text", "text", 20 * _MB, input_kind="file"),
    # Vision ------------------------------------------------------------------
    ToolSpec("ocr", "OcrExtract", "vision", "vision", 20 * _MB, input_kind="image"),
    ToolSpec(
        "anonymize",
        "Anonymize",
        "vision",
        "vision",
        10 * _MB,
        input_kind="image",
        result_kind="image",
    ),
    ToolSpec("alttext", "AltText", "vision", "vision", 10 * _MB, input_kind="image"),
    ToolSpec("objectcount", "ObjectCount", "vision", "vision", 10 * _MB, input_kind="image"),
    # Audio -------------------------------------------------------------------
    ToolSpec(
        "transcribe",
        "Transcribe",
        "audio",
        "audio",
        25 * _MB,
        input_kind="audio",
        result_kind="json",
    ),
    ToolSpec("tts", "Tts", "audio", "audio", 100 * _KB, input_kind="text", result_kind="audio"),
    ToolSpec(
        "audio-enhance",
        "AudioEnhance",
        "audio",
        "audio",
        25 * _MB,
        input_kind="audio",
        result_kind="audio",
    ),
    ToolSpec(
        "voicechat",
        "VoiceChat",
        "audio",
        "audio",
        25 * _MB,
        input_kind="audio",
        result_kind="audio",
    ),
)

CATALOG: dict[str, ToolSpec] = {tool.slug: tool for tool in _TOOLS}
SLUGS: tuple[str, ...] = tuple(CATALOG)


def get_tool(slug: str) -> ToolSpec:
    """Return the ToolSpec for ``slug`` or raise ``KeyError`` if unknown."""
    return CATALOG[slug]


def queue_for(slug: str) -> str | None:
    return CATALOG[slug].queue
