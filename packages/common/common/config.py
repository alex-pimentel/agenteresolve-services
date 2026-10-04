"""Central configuration for the AI services platform.

Every external dependency (Redis, Postgres, R2, LLM/embeddings/OCR/vision/audio/TTS,
Clerk) is reachable through URL + key environment variables so a component can be moved
to another VPS by changing env only.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Broker / ephemeral state -------------------------------------------------
    redis_url: str | None = None
    job_ttl_seconds: int = 86_400  # 24h

    # Cloudflare R2 (S3-compatible) -------------------------------------------
    r2_endpoint: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str = "tmp"
    r2_region: str = "auto"
    r2_presign_seconds: int = 3_600

    # Clerk auth (optional; anonymous allowed when unset) ----------------------
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None
    clerk_audience: str | None = None

    # LLM (OpenAI-compatible; default OpenRouter) ------------------------------
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "openai/gpt-4o-mini"
    llm_timeout: float = 60.0

    # Embeddings (OpenAI-compatible) ------------------------------------------
    embeddings_base_url: str | None = None
    embeddings_api_key: str | None = None
    embeddings_model: str = "text-embedding-3-small"

    # Vision / OCR / audio / TTS inference ------------------------------------
    ocr_url: str | None = None
    ocr_key: str | None = None
    vision_url: str | None = None
    vision_key: str | None = None
    audio_url: str | None = None
    audio_key: str | None = None
    tts_url: str | None = None
    tts_key: str | None = None

    # Outbound fetch guard (SEO URL import) -----------------------------------
    fetch_timeout: float = 10.0
    ssrf_block_private: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
