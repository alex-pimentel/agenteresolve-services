"""Provider contracts.

Each capability has a small Protocol so implementations (remote HTTP or local model) are
interchangeable. The factory in :mod:`common.providers.factory` chooses based on env:
if ``*_URL`` is set the remote endpoint is used, otherwise a local backend is loaded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ProviderUnavailable(RuntimeError):
    """Raised when a capability has no usable backend configured."""


class Capability(StrEnum):
    llm = "llm"
    embeddings = "embeddings"
    ocr = "ocr"
    vision = "vision"
    audio = "audio"
    tts = "tts"


@dataclass(frozen=True)
class ProviderConfig:
    capability: Capability
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout: float = 60.0

    @property
    def is_remote(self) -> bool:
        return bool(self.base_url)


# --- value objects ---------------------------------------------------------------


@dataclass
class OcrBlock:
    text: str
    bbox: list[float] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class Detection:
    label: str
    bbox: list[float] = field(default_factory=list)
    score: float = 0.0


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class Transcription:
    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str | None = None


# --- protocols -------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str: ...


@runtime_checkable
class EmbeddingsProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class OcrProvider(Protocol):
    is_remote: bool

    def extract(
        self, data: bytes, *, content_type: str, lang: str | None = None
    ) -> list[OcrBlock]: ...


@runtime_checkable
class VisionProvider(Protocol):
    is_remote: bool

    def caption(self, data: bytes, *, content_type: str) -> str: ...

    def detect(
        self, data: bytes, *, content_type: str, labels: list[str] | None = None
    ) -> list[Detection]: ...


@runtime_checkable
class AudioProvider(Protocol):
    is_remote: bool

    def transcribe(
        self, data: bytes, *, content_type: str, lang: str | None = None
    ) -> Transcription: ...

    def enhance(self, data: bytes, *, content_type: str, mode: str = "denoise") -> bytes: ...


@runtime_checkable
class TtsProvider(Protocol):
    is_remote: bool

    def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        lang: str | None = None,
        speed: float = 1.0,
    ) -> bytes: ...
