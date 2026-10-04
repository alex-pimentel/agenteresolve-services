"""Pydantic request schemas for gateway endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TextJobRequest(BaseModel):
    text: str = Field(min_length=1)


class TranslateRequest(TextJobRequest):
    target: str
    tone: str = "neutral"


class FeedbackRequest(TextJobRequest):
    items: list[str] | None = None


class SeoRequest(BaseModel):
    topic: str | None = None
    url: str | None = None
    lang: str = "pt"
    tone: str = "neutral"
    keyword: str = ""


class TtsRequest(TextJobRequest):
    voice: str | None = None
    lang: str = "pt"
    speed: float = 1.0


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class VoiceChatSessionRequest(BaseModel):
    persona: str = "a helpful assistant"
    lang: str = "pt"


class VoiceChatTurnResponse(BaseModel):
    session_id: str
    transcript: str
    reply_text: str
    reply_audio_url: str | None = None


__all__ = [
    "AskRequest",
    "FeedbackRequest",
    "SeoRequest",
    "TextJobRequest",
    "TranslateRequest",
    "TtsRequest",
    "VoiceChatSessionRequest",
    "VoiceChatTurnResponse",
]
