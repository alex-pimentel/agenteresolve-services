"""Reference tool: Translator (LLM-only).

Translates text or extracted document text between languages while preserving markdown
structure, code blocks and placeholders. Content only transits worker memory and the R2
``tmp`` bucket; nothing is persisted.
"""

from __future__ import annotations

from common.providers.base import ProviderUnavailable

from worker.handlers.base import HandlerContext, HandlerResult

SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {
        "pt",
        "en",
        "es",
        "fr",
        "de",
        "it",
        "nl",
        "pl",
        "sv",
        "tr",
        "ru",
        "ar",
        "hi",
        "ja",
        "ko",
        "zh",
    }
)

_SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into the requested "
    "target language. Preserve markdown structure, code blocks, placeholders, URLs and "
    "inline formatting exactly. Return only the translation, with no preamble or notes."
)


class UnsupportedLanguage(ValueError):
    def __init__(self, target: str) -> None:
        super().__init__(
            f"Unsupported target language: {target!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
        )
        self.target = target


def handle_translate(ctx: HandlerContext) -> HandlerResult:
    if ctx.llm is None:
        raise ProviderUnavailable("translate requires an LLM provider")

    raw = ctx.object_store.get_bytes(ctx.input_key)
    text = raw.decode("utf-8", errors="replace")

    target = str(ctx.params.get("target") or "").strip().lower()
    if target not in SUPPORTED_LANGUAGES:
        raise UnsupportedLanguage(target)

    tone = str(ctx.params.get("tone") or "neutral")
    prompt = f"Target language: {target}\nTone: {tone}\n\nText to translate:\n{text}"
    translated = ctx.llm.complete(prompt, system=_SYSTEM_PROMPT)

    key = f"results/translate/{ctx.task_id}/result.txt"
    return HandlerResult(
        key=key,
        data=translated.encode("utf-8"),
        content_type="text/plain; charset=utf-8",
    )
