"""Oracle media service: heavy YouTube -> MP3 conversion (yt-dlp + ffmpeg).

Runs on the Oracle host (tailnet-only). The Coolify workers call
``POST /youtube-mp3`` with ``{"url", "quality"}`` and stream the MP3 back;
the gateway/worker layer owns auth, credits and validation. This service
re-validates defensively and never touches user data beyond the temp dir.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # nosec B404 - fixed argv (yt-dlp/ffmpeg), no shell
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
}

_ID_PATTERNS = (
    re.compile(r"[?&]v=([\w-]{6,20})"),
    re.compile(r"^/(?:shorts|embed|live|v)/([\w-]{6,20})(?:[/?#]|$)"),
    re.compile(r"^/([\w-]{6,20})(?:[/?#]|$)"),
)

_QUALITIES = {"128", "192", "320"}
_MAX_VIDEO_SECONDS = 2 * 60 * 60  # 2h safety cap

_MEDIA_KEY = os.environ.get("MEDIA_KEY", "")

app = FastAPI(title="agenteresolve-media")


def _video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="URL do YouTube inválida.")
    host = (parsed.hostname or "").lower()
    if host not in _YT_HOSTS:
        raise HTTPException(status_code=422, detail="Apenas links do YouTube são aceitos.")
    if match := _ID_PATTERNS[0].search(f"{parsed.path}?{parsed.query}"):
        return match.group(1)
    if match := _ID_PATTERNS[1].search(parsed.path):
        return match.group(1)
    if host == "youtu.be" and (match := _ID_PATTERNS[2].search(parsed.path)):
        return match.group(1)
    raise HTTPException(status_code=422, detail="Não encontrei o id do vídeo nessa URL.")


@app.get("/")
def root() -> dict[str, str | None]:
    import importlib.metadata
    import subprocess as _sp

    try:
        yt_dlp_version: str | None = importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        yt_dlp_version = None

    def _ver(binary: str | None) -> str | None:
        if not binary:
            return None
        try:
            out = _sp.run([binary, "--version"], capture_output=True, timeout=10)
            return out.stdout.decode().strip() or out.stderr.decode().strip() or "?"
        except Exception:
            return "exec-failed"

    return {
        "status": "ok",
        "service": "media",
        "node": shutil.which("node"),
        "node_version": _ver(shutil.which("node")),
        "deno": shutil.which("deno"),
        "deno_version": _ver(shutil.which("deno")),
        "ffmpeg": shutil.which("ffmpeg"),
        "yt_dlp": shutil.which("yt-dlp"),
        "yt_dlp_version": yt_dlp_version,
    }


@app.get("/health")
def health() -> dict[str, str]:
    ytdlp = shutil.which("yt-dlp")
    ffmpeg = shutil.which("ffmpeg")
    if not ytdlp or not ffmpeg:
        raise HTTPException(status_code=503, detail="yt-dlp/ffmpeg not installed")
    return {"status": "ok"}


@app.post("/youtube-mp3")
def youtube_mp3(body: dict, authorization: str | None = Header(default=None)) -> FileResponse:
    if _MEDIA_KEY:
        token = (authorization or "").removeprefix("Bearer ").strip()
        if token != _MEDIA_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized")
    url = str(body.get("url") or "").strip()
    quality = str(body.get("quality") or "192").strip()
    if quality not in _QUALITIES:
        raise HTTPException(status_code=422, detail="Qualidade inválida: use 128, 192 ou 320.")
    video_id = _video_id(url)

    ytdlp = shutil.which("yt-dlp")
    ffmpeg = shutil.which("ffmpeg")
    if not ytdlp or not ffmpeg:
        raise HTTPException(status_code=503, detail="yt-dlp/ffmpeg not installed")

    tmp = tempfile.mkdtemp(prefix="yt2mp3-")
    out = str(Path(tmp) / "audio.%(ext)s")
    try:
        subprocess.run(  # nosec B603 - fixed argv, no shell
            [
                ytdlp,
                "--no-playlist",
                "--max-downloads",
                "1",
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
            ],
            check=True,
            capture_output=True,
            timeout=280,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
        err_lines = [line for line in stderr.splitlines() if "ERROR" in line]
        detail = "; ".join(err_lines[-3:]) or stderr[-2000:]
        raise HTTPException(
            status_code=422, detail=f"Falha ao baixar/convertar: {detail[-2000:]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504, detail="Tempo limite de conversão excedido."
        ) from exc
    mp3 = Path(tmp) / "audio.mp3"
    if not mp3.exists():
        raise HTTPException(status_code=422, detail="Conversão não gerou o MP3.")
    return FileResponse(
        path=str(mp3),
        media_type="audio/mpeg",
        filename=f"youtube-{video_id}-{quality}k.mp3",
    )
