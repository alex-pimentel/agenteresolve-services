# Oracle media service: yt-dlp + ffmpeg for YouTube -> MP3.
# Deployed via Coolify on the Oracle server (tailnet-only, port 8001).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml ./
COPY media ./media

RUN uv sync --frozen --no-dev --package media

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

CMD ["uvicorn", "media.main:app", "--host", "0.0.0.0", "--port", "8001"]
