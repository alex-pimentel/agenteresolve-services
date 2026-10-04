"""Audio tool handlers (transcription, TTS, enhancement)."""

from __future__ import annotations

from common.jsonutil import json_bytes
from common.providers.base import ProviderUnavailable

from worker.handlers.base import HandlerContext, HandlerResult

_TRANSCRIBE_SUMMARY_SYSTEM = (
    "You summarize transcripts. Return ONLY a JSON object: "
    '{"summary": string, "topics": [string], "action_items": [string]}.'
)


def _to_srt(segments: list[dict[str, float | str]]) -> str:
    def stamp(seconds: float) -> str:
        millis = int(round(seconds * 1000))
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        secs, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        start = float(segment["start"])
        end = float(segment["end"])
        lines.append(f"{index}\n{stamp(start)} --> {stamp(end)}\n{segment['text']}\n")
    return "\n".join(lines)


def handle_transcribe(ctx: HandlerContext) -> HandlerResult:
    if ctx.audio is None:
        raise ProviderUnavailable("transcribe requires an audio provider")
    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "audio/wav")
    lang_param = ctx.params.get("lang")
    lang = None if not lang_param or lang_param == "auto" else str(lang_param)

    transcription = ctx.audio.transcribe(raw, content_type=content_type, lang=lang)
    segments = [
        {"start": segment.start, "end": segment.end, "text": segment.text}
        for segment in transcription.segments
    ]

    summarize = str(ctx.params.get("summarize", "false")).lower() in ("1", "true", "yes")
    summary: dict[str, object] | None = None
    if summarize and ctx.llm is not None and transcription.text.strip():
        from common.jsonutil import parse_json_object

        try:
            summary = parse_json_object(
                ctx.llm.complete(transcription.text, system=_TRANSCRIBE_SUMMARY_SYSTEM)
            )
        except ValueError:
            summary = {"summary": "", "topics": [], "action_items": []}

    payload = {
        "text": transcription.text,
        "segments": segments,
        "language": transcription.language or lang,
        "srt": _to_srt(segments),
        "summary": summary,
    }
    key = f"results/transcribe/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")


def handle_tts(ctx: HandlerContext) -> HandlerResult:
    if ctx.tts is None:
        raise ProviderUnavailable("tts requires a TTS provider")
    raw = ctx.object_store.get_bytes(ctx.input_key)
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("No text provided for synthesis")

    voice = ctx.params.get("voice")
    lang = ctx.params.get("lang")
    speed = float(ctx.params.get("speed") or 1.0)

    audio = ctx.tts.synthesize(
        text,
        voice=str(voice) if voice else None,
        lang=str(lang) if lang else None,
        speed=speed,
    )
    key = f"results/tts/{ctx.task_id}/result.mp3"
    return HandlerResult(key=key, data=audio, content_type="audio/mpeg")


def handle_audio_enhance(ctx: HandlerContext) -> HandlerResult:
    if ctx.audio is None:
        raise ProviderUnavailable("audio-enhance requires an audio provider")
    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "audio/wav")
    mode = str(ctx.params.get("mode") or "denoise")
    if mode not in ("denoise", "voice-isolate", "normalize"):
        raise ValueError(f"Unknown enhance mode: {mode!r}")

    enhanced = ctx.audio.enhance(raw, content_type=content_type, mode=mode)
    key = f"results/audio-enhance/{ctx.task_id}/result.wav"
    return HandlerResult(key=key, data=enhanced, content_type="audio/wav")
