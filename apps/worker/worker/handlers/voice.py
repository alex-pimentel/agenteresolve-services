"""VoiceChat: STT -> LLM -> TTS turns within an ephemeral session."""

from __future__ import annotations

import json
import uuid
from typing import Any

from common.providers.base import ProviderUnavailable
from common.sessions import get_session_store

from worker.handlers.base import HandlerContext, HandlerResult


def handle_voicechat(ctx: HandlerContext) -> HandlerResult:
    if ctx.audio is None or ctx.llm is None or ctx.tts is None:
        raise ProviderUnavailable("voicechat requires audio, LLM and TTS providers")

    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "audio/wav")
    persona = str(ctx.params.get("persona") or "a helpful assistant")
    lang = str(ctx.params.get("lang") or "pt")
    session_id = str(ctx.params.get("session_id") or "")

    store = get_session_store()
    session = store.get(session_id) if session_id else None
    if session is None:
        session_id = uuid.uuid4().hex
        session = store.create(session_id, "voicechat", history=[], persona=persona, lang=lang)

    transcription = ctx.audio.transcribe(raw, content_type=content_type, lang=lang)
    history: list[dict[str, str]] = session.data["history"]

    system = f"You are {persona}. Reply concisely in language '{lang}'."
    context = "\n".join(f"{turn['role']}: {turn['text']}" for turn in history[-6:])
    prompt = f"{context}\nuser: {transcription.text}".strip()
    reply = ctx.llm.complete(prompt, system=system)

    audio = ctx.tts.synthesize(reply, lang=lang)
    history.append({"role": "user", "text": transcription.text})
    history.append({"role": "assistant", "text": reply})

    payload = {
        "session_id": session_id,
        "transcript": transcription.text,
        "reply_text": reply,
        "turns": len(history) // 2,
    }
    ctx.object_store.put_bytes(
        f"results/voicechat/{ctx.task_id}/turn.json",
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )
    audio_key = f"results/voicechat/{ctx.task_id}/reply.mp3"
    return HandlerResult(key=audio_key, data=audio, content_type="audio/mpeg")


__all__: list[Any] = ["handle_voicechat"]
