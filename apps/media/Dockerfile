# Oracle media service: yt-dlp + ffmpeg for YouTube -> MP3.
# Deployed via Coolify on the Oracle server (tailnet-only, port 8001).
#
# NOTE: Coolify builds with context = base_directory (/apps/media), so this
# Dockerfile is intentionally self-contained (plain pip, no uv workspace).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && (command -v node || ln -s "$(command -v nodejs)" /usr/local/bin/node) \
    && node --version \
    && python3 -c "import shutil; assert shutil.which('node'), 'node ausente no PATH'"

WORKDIR /app

COPY media ./media

RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "yt-dlp==2026.8.19"

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "media.main:app", "--host", "0.0.0.0", "--port", "8001"]
