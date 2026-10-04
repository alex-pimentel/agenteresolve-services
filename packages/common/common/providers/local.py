"""Lazy local backends for the non-LLM capabilities.

Every heavy model import happens *inside* the method, never at module import time, so the
worker image stays light until a capability is actually used. When the optional dependency
or model is missing the method raises :class:`ProviderUnavailable` with an actionable
message instead of crashing the worker at startup.
"""

from __future__ import annotations

import importlib
import io
import json
from typing import Any

from common.providers.base import (
    Detection,
    OcrBlock,
    ProviderUnavailable,
    Transcription,
    TranscriptSegment,
)


def _require(module: str) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - depends on optional deps
        raise ProviderUnavailable(
            f"Optional dependency '{module}' is not installed. Install the local model "
            f"extra or configure the matching remote *_URL provider."
        ) from exc


def _load_image(data: bytes) -> Any:
    Image = _require("PIL.Image")
    return Image.open(io.BytesIO(data)).convert("RGB")


# --- OCR --------------------------------------------------------------------------


class LocalOcrProvider:
    """Tesseract-backed OCR (optional ``pytesseract`` dependency)."""

    is_remote = False

    def __init__(self, model: str | None = None, **_: Any) -> None:
        self.model = model

    def extract(self, data: bytes, *, content_type: str, lang: str | None = None) -> list[OcrBlock]:
        import os
        import tempfile

        pytesseract = _require("pytesseract")
        image = _load_image(data)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = os.path.join(tmp, "image.png")
            image.save(tmp_path)
            raw = pytesseract.image_to_data(
                tmp_path, lang=lang or "eng", output_type=pytesseract.Output.DICT
            )
        blocks: list[OcrBlock] = []
        for index, text in enumerate(raw.get("text", [])):
            if not str(text).strip():
                continue
            bbox = [
                float(raw["left"][index]),
                float(raw["top"][index]),
                float(raw["left"][index] + raw["width"][index]),
                float(raw["top"][index] + raw["height"][index]),
            ]
            confidence = float(raw["conf"][index]) / 100.0
            blocks.append(OcrBlock(text=str(text), bbox=bbox, confidence=confidence))
        return blocks


# --- Vision -----------------------------------------------------------------------


class LocalVisionProvider:
    """BLIP captioning + YOLO detection (optional ``transformers``/``ultralytics``)."""

    is_remote = False

    def __init__(self, model: str | None = None, **_: Any) -> None:
        self.model = model
        self._caption_pipeline: Any = None
        self._detector: Any = None

    def _captioner(self) -> Any:
        if self._caption_pipeline is None:
            transformers = _require("transformers")
            self._caption_pipeline = transformers.pipeline(
                "image-to-text", model="Salesforce/blip-image-captioning-base"
            )
        return self._caption_pipeline

    def caption(self, data: bytes, *, content_type: str) -> str:
        image = _load_image(data)
        output = self._captioner()(image)
        if isinstance(output, list) and output:
            return str(output[0].get("generated_text", "")).strip()
        return str(output).strip()

    def _yolo(self) -> Any:
        if self._detector is None:
            ultralytics = _require("ultralytics")
            self._detector = ultralytics.YOLO("yolov8n.pt")
        return self._detector

    def detect(
        self, data: bytes, *, content_type: str, labels: list[str] | None = None
    ) -> list[Detection]:
        import numpy as np

        image = _load_image(data)
        result = self._yolo()(np.array(image), verbose=False)[0]
        names = result.names
        detections: list[Detection] = []
        for box in result.boxes:
            label = str(names[int(box.cls)])
            if labels and label not in labels:
                continue
            coords = [float(value) for value in box.xyxy[0].tolist()]
            detections.append(Detection(label=label, bbox=coords, score=float(box.conf)))
        return detections


# --- Audio ------------------------------------------------------------------------


class LocalAudioProvider:
    """faster-whisper transcription + ffmpeg denoise/normalize."""

    is_remote = False

    def __init__(self, model: str | None = None, **_: Any) -> None:
        self.model = model or "tiny"
        self._whisper: Any = None

    def _model(self) -> Any:
        if self._whisper is None:
            faster_whisper = _require("faster_whisper")
            self._whisper = faster_whisper.WhisperModel(self.model)
        return self._whisper

    def transcribe(
        self, data: bytes, *, content_type: str, lang: str | None = None
    ) -> Transcription:
        import os
        import tempfile

        model = self._model()
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "audio")
            with open(audio_path, "wb") as handle:
                handle.write(data)
            segments, info = model.transcribe(audio_path, language=lang)
            collected = [
                TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip())
                for seg in segments
            ]
        text = " ".join(seg.text for seg in collected).strip()
        return Transcription(text=text, segments=collected, language=info.language)

    def enhance(self, data: bytes, *, content_type: str, mode: str = "denoise") -> bytes:
        import os
        import shutil
        import subprocess  # nosec B404 - fixed ffmpeg argv, no shell, no user input
        import tempfile

        filters = {
            "denoise": "highpass=f=80,afftdn,lowpass=f=8000",
            "voice-isolate": "highpass=f=100,afftdn,lowpass=f=6000",
            "normalize": "loudnorm=I=-16:TP=-1.5:LRA=11",
        }
        if mode not in filters:
            raise ProviderUnavailable(f"Unknown enhance mode: {mode!r}")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise ProviderUnavailable("ffmpeg is not installed; cannot enhance audio")
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "in.wav")
            out_path = os.path.join(tmp, "out.wav")
            with open(in_path, "wb") as handle:
                handle.write(data)
            try:
                subprocess.run(  # nosec B603 - resolved absolute path, list argv, no shell
                    [ffmpeg, "-y", "-i", in_path, "-af", filters[mode], out_path],
                    check=True,
                    capture_output=True,
                )
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:  # pragma: no cover
                raise ProviderUnavailable(f"ffmpeg failed to enhance audio: {exc}") from exc
            with open(out_path, "rb") as handle:
                return handle.read()


# --- TTS --------------------------------------------------------------------------


class LocalTtsProvider:
    """Piper TTS (optional ``piper-tts`` dependency)."""

    is_remote = False

    def __init__(self, model: str | None = None, **_: Any) -> None:
        self.model = model

    def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        lang: str | None = None,
        speed: float = 1.0,
    ) -> bytes:
        piper = _require("piper")
        voice_name = voice or _PIPER_DEFAULT.get((lang or "en")[:2], "en_US-lessac-medium")
        try:
            piper_voice = piper.PiperVoice.load(voice_name)
            stream = piper_voice.synthesize(text, length_scale=1.0 / max(speed, 0.1))
            buffer = io.BytesIO()
            for chunk in stream:
                buffer.write(chunk.audio_int16_bytes)
            return buffer.getvalue()
        except Exception as exc:  # noqa: BLE001 - mapped to a clear provider error
            raise ProviderUnavailable(
                f"Piper synthesis failed for voice {voice_name!r}: {exc}"
            ) from exc


_PIPER_DEFAULT: dict[str, str] = {
    "pt": "pt_BR-faber-medium",
    "en": "en_US-lessac-medium",
    "es": "es_ES-davefx-medium",
}


# --- Embeddings -------------------------------------------------------------------


class HashingEmbeddingsProvider:
    """Deterministic in-process embeddings fallback for tests and offline dev.

    A small bag-of-words hashing vectorizer: not semantic, but stable and dependency-free,
    which keeps the RAG plumbing exercised without a network call.
    """

    is_remote = False
    _DIM = 256

    def __init__(self, model: str | None = None, **_: Any) -> None:
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import math

        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self._DIM
            for token in text.lower().split():
                digest = hashlib.sha1(token.encode("utf-8"), usedforsecurity=False).digest()
                index = int.from_bytes(digest[:2], "big") % self._DIM
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


__all__ = [
    "HashingEmbeddingsProvider",
    "LocalAudioProvider",
    "LocalOcrProvider",
    "LocalTtsProvider",
    "LocalVisionProvider",
]


def _unused() -> None:  # pragma: no cover
    json.dumps({})
