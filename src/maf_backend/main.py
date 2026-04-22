from __future__ import annotations

from fastapi import FastAPI

from maf_backend.api.routes import router
from maf_backend.infrastructure.auth import BearerTokenAuthenticator
from maf_backend.settings import Settings, get_settings


def create_app(settings: Settings | None = None, service=None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(title=app_settings.app_name)
    app.state.settings = app_settings
    app.state.authenticator = BearerTokenAuthenticator(app_settings)
    app.state.analysis_service = service
    app.include_router(router)
    return app


app = create_app()
