"""Gateway application factory."""

from common.config import get_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.routes import router


def create_app() -> FastAPI:
    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
    app = FastAPI(
        title="Agenteresolve AI Services Gateway",
        version="0.1.0",
        description="Unified gateway for the Agenteresolve AI tool catalogue.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key"],
    )
    app.include_router(router)
    return app


app = create_app()
