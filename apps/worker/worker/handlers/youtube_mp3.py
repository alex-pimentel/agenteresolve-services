"""YouTube -> MP3 handler.

Flow: frontend sends ``{"text": "<youtube url>", "quality": "128|192|320"}``.
The gateway stores the URL as bytes; this handler validates the URL, then
converts preferably via the Oracle media endpoint (``MEDIA_URL`` — the host
that owns yt-dlp + ffmpeg), falling back to local yt-dlp + ffmpeg for dev.

Only URLs the user is allowed to convert are accepted: watch/shorts/embed
on youtube.com / youtube-nocookie.com / music.youtube.com and youtu.be.
Anything else is a 422-style ``ValueError`` (reported on the job, refunded).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess  # nosec B404 - fixed argv (yt-dlp/ffmpeg), no shell
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from common.providers.base import ProviderUnavailable

from worker.handlers.base import HandlerContext, HandlerResult

_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
}

# watch?v=... first, then /shorts|embed|live|v/<id>, then bare youtu.be/<id>
_ID_PATTERNS = (
    re.compile(r"[?&]v=([\w-]{6,20})"),
    re.compile(r"^/(?:shorts|embed|live|v)/([\w-]{6,20})(?:[/?#]|$)"),
    re.compile(r"^/([\w-]{6,20})(?:[/?#]|$)"),
)

_QUALITIES = {"128": "128", "192": "192", "320": "320"}

_MAX_VIDEO_SECONDS = 2 * 60 * 60  # 2h safety cap


def extract_video_id(url: str) -> str:
    """Return the 6-20 char YouTube video id or raise ``ValueError``."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL do YouTube inválida: use http(s).")
    host = (parsed.hostname or "").lower()
    if host not in _YT_HOSTS:
        raise ValueError("URL inválida: apenas links do YouTube são aceitos.")
    haystack = parsed.path or ""
    query = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
    match = _ID_PATTERNS[0].search(query)
    if match:
        return match.group(1)
    match = _ID_PATTERNS[1].search(haystack)
    if match:
        return match.group(1)
    if host == "youtu.be":
        match = _ID_PATTERNS[2].search(haystack)
        if match:
            return match.group(1)
    raise ValueError("Não encontrei o id do vídeo nessa URL do YouTube.")


def _quality(params: dict) -> str:
    raw = str(params.get("quality") or "192").strip()
    if raw not in _QUALITIES:
        raise ValueError("Qualidade inválida: use 128, 192 ou 320.")
    return raw


def _via_oracle(url: str, quality: str, media_url: str, media_key: str | None) -> bytes:
    headers = {"Content-Type": "application/json"}
    if media_key:
        headers["Authorization"] = f"Bearer {media_key}"
    try:
        response = httpx.post(
            f"{media_url.rstrip('/')}/youtube-mp3",
            content=json.dumps({"url": url, "quality": quality}).encode(),
            headers=headers,
            timeout=300.0,
        )
    except httpx.HTTPError as exc:
        raise ProviderUnavailable(f"media endpoint unreachable: {exc}") from exc
    if response.status_code == 404:
        raise ProviderUnavailable("media endpoint has no /youtube-mp3 route")
    if response.status_code >= 400:
        raise ProviderUnavailable(f"media endpoint failed: HTTP {response.status_code}")
    data = response.content
    if not data:
        raise ProviderUnavailable("media endpoint returned an empty file")
    return data


def _via_local(url: str, quality: str) -> bytes:
    ytdlp = shutil.which("yt-dlp")
    ffmpeg = shutil.which("ffmpeg")
    if not ytdlp or not ffmpeg:
        raise ProviderUnavailable(
            "youtube2mp3 requires the Oracle media endpoint (yt-dlp + ffmpeg)"
        )
    with tempfile.TemporaryDirectory(prefix="yt2mp3-") as tmp:
        out = str(Path(tmp) / "audio.%(ext)s")
        cmd = [
            ytdlp,
            "--no-playlist",
            "--match-filter",
            f"duration < {_MAX_VIDEO_SECONDS}",
            "--remote-components",
            "ejs:github",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            f"{quality}K",
            "--ffmpeg-location",
            ffmpeg,
            "-o",
            out,
            url,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=280)  # nosec B603
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
            err_lines = [line for line in stderr.splitlines() if "ERROR" in line]
            detail = "; ".join(err_lines[-2:]) or stderr[-500:]
            raise ValueError(f"Falha ao baixar/convertar: {detail[-500:]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Tempo limite de conversão excedido (vídeo muito longo?).") from exc
        mp3 = Path(tmp) / "audio.mp3"
        if not mp3.exists():
            raise ValueError("Conversão não gerou o MP3 (vídeo indisponível ou restrito?).")
        return mp3.read_bytes()


def handle_youtube2mp3(ctx: HandlerContext) -> HandlerResult:
    from common.config import get_settings

    raw = ctx.object_store.get_bytes(ctx.input_key).decode("utf-8", errors="replace").strip()
    if not raw:
        raise ValueError("Informe a URL do vídeo do YouTube.")
    if len(raw) > 4 * 1024:
        raise ValueError("URL muito longa.")
    video_id = extract_video_id(raw)
    quality = _quality(ctx.params)

    settings = get_settings()
    if settings.media_url:
        data = _via_oracle(raw, quality, settings.media_url, settings.media_key)
    else:
        data = _via_local(raw, quality)

    key = f"results/youtube2mp3/{ctx.task_id}/{video_id}-{quality}k.mp3"
    return HandlerResult(key=key, data=data, content_type="audio/mpeg")


__all__ = ["extract_video_id", "handle_youtube2mp3"]
