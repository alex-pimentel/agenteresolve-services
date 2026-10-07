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
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && (curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh || echo "deno indisponível, seguindo só com node") \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version

WORKDIR /app

COPY media ./media

RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "yt-dlp==2026.8.19"

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "media.main:app", "--host", "0.0.0.0", "--port", "8001"]
