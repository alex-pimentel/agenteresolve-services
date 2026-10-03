"""Canonical tool catalogue: the single source of truth for the 16 slugs.

The gateway uses this registry to route requests and to expose HTTP 501 for tools that
are registered but not implemented yet. The worker uses the queue field for routing.
"""

from dataclasses import dataclass
from typing import Literal

Category = Literal["client", "text", "vision", "audio"]
Queue = Literal["text", "vision", "audio"]

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
    implemented: bool = False
    notes: str = ""


_TOOLS: tuple[ToolSpec, ...] = (
    # Client-side (browser, Cloudflare Pages) --------------------------------
    ToolSpec(
        "louder", "Louder", "client", None, 25 * _MB, notes="client-side only; no gateway endpoint"
    ),
    # Text / LLM --------------------------------------------------------------
    ToolSpec("docuextract", "DocuExtract", "text", "text", 20 * _MB),
    ToolSpec("askyourdocs", "AskYourDocs", "text", "text", 20 * _MB),
    ToolSpec("datachat", "DataChat", "text", "text", 20 * _MB),
    ToolSpec("feedback", "FeedbackClassifier", "text", "text", 200 * _KB),
    ToolSpec("seo", "SEOContent", "text", "text", 200 * _KB),
    ToolSpec("translate", "Translator", "text", "text", 10 * _MB, implemented=True),
    ToolSpec("contracts", "ContractChecker", "text", "text", 20 * _MB),
    # Vision ------------------------------------------------------------------
    ToolSpec("ocr", "OcrExtract", "vision", "vision", 20 * _MB),
    ToolSpec("anonymize", "Anonymize", "vision", "vision", 10 * _MB),
    ToolSpec("alttext", "AltText", "vision", "vision", 10 * _MB),
    ToolSpec("objectcount", "ObjectCount", "vision", "vision", 10 * _MB),
    # Audio -------------------------------------------------------------------
    ToolSpec("transcribe", "Transcribe", "audio", "audio", 25 * _MB),
    ToolSpec("tts", "Tts", "audio", "audio", 100 * _KB),
    ToolSpec("audio-enhance", "AudioEnhance", "audio", "audio", 25 * _MB),
    ToolSpec("voicechat", "VoiceChat", "audio", "audio", 25 * _MB),
)

CATALOG: dict[str, ToolSpec] = {tool.slug: tool for tool in _TOOLS}
SLUGS: tuple[str, ...] = tuple(CATALOG)


def get_tool(slug: str) -> ToolSpec:
    """Return the ToolSpec for ``slug`` or raise ``KeyError`` if unknown."""
    return CATALOG[slug]


def queue_for(slug: str) -> str | None:
    return CATALOG[slug].queue
