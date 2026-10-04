"""Tool handler registry mapping every gateway slug to its handler."""

from collections.abc import Callable

from worker.handlers.audio import handle_audio_enhance, handle_transcribe, handle_tts
from worker.handlers.base import HandlerContext, HandlerResult
from worker.handlers.data import handle_datachat
from worker.handlers.rag import handle_askyourdocs
from worker.handlers.text import (
    handle_contracts,
    handle_docuextract,
    handle_feedback,
    handle_seo,
)
from worker.handlers.translate import handle_translate
from worker.handlers.vision import (
    handle_alttext,
    handle_anonymize,
    handle_objectcount,
    handle_ocr,
)
from worker.handlers.voice import handle_voicechat

Handler = Callable[[HandlerContext], HandlerResult]

HANDLERS: dict[str, Handler] = {
    "docuextract": handle_docuextract,
    "askyourdocs": handle_askyourdocs,
    "datachat": handle_datachat,
    "feedback": handle_feedback,
    "seo": handle_seo,
    "translate": handle_translate,
    "contracts": handle_contracts,
    "ocr": handle_ocr,
    "anonymize": handle_anonymize,
    "alttext": handle_alttext,
    "objectcount": handle_objectcount,
    "transcribe": handle_transcribe,
    "tts": handle_tts,
    "audio-enhance": handle_audio_enhance,
    "voicechat": handle_voicechat,
}


def get_handler(slug: str) -> Handler:
    handler = HANDLERS.get(slug)
    if handler is None:
        raise KeyError(f"No handler registered for tool '{slug}'")
    return handler


__all__ = ["HANDLERS", "Handler", "get_handler"]
