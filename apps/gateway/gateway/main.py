"""Gateway application factory."""

from fastapi import FastAPI

from gateway.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agenteresolve AI Services Gateway",
        version="0.1.0",
        description="Unified gateway for the Agenteresolve AI tool catalogue.",
    )
    app.include_router(router)
    return app


app = create_app()
