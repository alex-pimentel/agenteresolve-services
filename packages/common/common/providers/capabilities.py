"""Remote and local implementations for non-LLM capabilities.

The interface is what matters for portability. Remote variants proxy to a service by URL
and key; local variants are defined in :mod:`common.providers.local` and lazily import
their heavy dependencies inside each method. The factory picks the remote path when
``*_URL`` is set, otherwise the local path.
"""

from __future__ import annotations

import httpx

from common.providers.base import (
    Detection,
    OcrBlock,
    Transcription,
    TranscriptSegment,
)
from common.providers.local import (
    HashingEmbeddingsProvider,
    LocalAudioProvider,
    LocalOcrProvider,
    LocalTtsProvider,
    LocalVisionProvider,
)


class _Base:
    is_remote = False

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.url = url.rstrip("/") if url else None
        self.key = key
        self.model = model
        self.timeout = timeout


def _remote_headers(key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


# --- embeddings ------------------------------------------------------------------


class RemoteEmbeddingsProvider(_Base):
    is_remote = True

    def embed(self, texts: list[str]) -> list[list[float]]:
        assert self.url is not None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.url}/embeddings",
                json={"model": self.model, "input": texts},
                headers=_remote_headers(self.key),
            )
            response.raise_for_status()
            data = response.json()
        return [item["embedding"] for item in data["data"]]


class LocalEmbeddingsProvider(HashingEmbeddingsProvider):
    """Deterministic offline embeddings used when ``EMBEDDINGS_BASE_URL`` is unset."""


# --- OCR -------------------------------------------------------------------------


class RemoteOcrProvider(_Base):
    is_remote = True

    def extract(self, data: bytes, *, content_type: str, lang: str | None = None) -> list[OcrBlock]:
        assert self.url is not None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.url}/ocr",
                files={"file": ("input", data, content_type)},
                data={"lang": lang} if lang else None,
                headers={"Authorization": f"Bearer {self.key}"} if self.key else None,
            )
            response.raise_for_status()
            payload = response.json()
        return [OcrBlock(**block) for block in payload.get("blocks", [])]


# --- vision ----------------------------------------------------------------------


class RemoteVisionProvider(_Base):
    is_remote = True

    def caption(self, data: bytes, *, content_type: str) -> str:
        assert self.url is not None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.url}/caption",
                files={"file": ("input", data, content_type)},
                headers={"Authorization": f"Bearer {self.key}"} if self.key else None,
            )
            response.raise_for_status()
            payload = response.json()
        return str(payload.get("caption", ""))

    def detect(
        self, data: bytes, *, content_type: str, labels: list[str] | None = None
    ) -> list[Detection]:
        assert self.url is not None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.url}/detect",
                files={"file": ("input", data, content_type)},
                data={"labels": ",".join(labels)} if labels else None,
                headers={"Authorization": f"Bearer {self.key}"} if self.key else None,
            )
            response.raise_for_status()
            payload = response.json()
        return [Detection(**item) for item in payload.get("detections", [])]


# --- audio -----------------------------------------------------------------------


class RemoteAudioProvider(_Base):
    is_remote = True

    def transcribe(
        self, data: bytes, *, content_type: str, lang: str | None = None
    ) -> Transcription:
        assert self.url is not None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.url}/transcribe",
                files={"file": ("input", data, content_type)},
                data={"lang": lang} if lang else None,
                headers={"Authorization": f"Bearer {self.key}"} if self.key else None,
            )
            response.raise_for_status()
            payload = response.json()
        segments = [TranscriptSegment(**segment) for segment in payload.get("segments", [])]
        return Transcription(
            text=payload.get("text", ""),
            segments=segments,
            language=payload.get("language"),
        )

    def enhance(self, data: bytes, *, content_type: str, mode: str = "denoise") -> bytes:
        assert self.url is not None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.url}/enhance",
                files={"file": ("input", data, content_type)},
                data={"mode": mode},
                headers={"Authorization": f"Bearer {self.key}"} if self.key else None,
            )
            response.raise_for_status()
            return response.content


# --- TTS -------------------------------------------------------------------------


class RemoteTtsProvider(_Base):
    is_remote = True

    def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        lang: str | None = None,
        speed: float = 1.0,
    ) -> bytes:
        assert self.url is not None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.url}/synthesize",
                json={"text": text, "voice": voice, "lang": lang, "speed": speed},
                headers=_remote_headers(self.key),
            )
            response.raise_for_status()
            return response.content


__all__ = [
    "LocalAudioProvider",
    "LocalEmbeddingsProvider",
    "LocalOcrProvider",
    "LocalTtsProvider",
    "LocalVisionProvider",
    "RemoteAudioProvider",
    "RemoteEmbeddingsProvider",
    "RemoteOcrProvider",
    "RemoteTtsProvider",
    "RemoteVisionProvider",
]
