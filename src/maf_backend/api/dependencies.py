from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from maf_backend.application.agent import AnalysisAgentRunner
from maf_backend.application.service import AnalysisService
from maf_backend.infrastructure.auth import BearerTokenAuthenticator
from maf_backend.infrastructure.repository import InMemoryAnalysisJobRepository
from maf_backend.infrastructure.sandbox.runner import DockerSandboxRunner
from maf_backend.settings import Settings, get_settings


def get_settings_dependency() -> Settings:
    return get_settings()


def get_authenticator(request: Request) -> BearerTokenAuthenticator:
    authenticator = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        raise RuntimeError("authenticator is not configured")
    return authenticator


async def get_current_owner(
    request: Request,
    authenticator: BearerTokenAuthenticator = Depends(get_authenticator),  # noqa: B008
) -> str:
    return await authenticator.authenticate(request)


def get_analysis_service(request: Request) -> AnalysisService:
    service = getattr(request.app.state, "analysis_service", None)
    if service is None:
        settings = getattr(request.app.state, "settings", None)
        if settings is None:
            raise RuntimeError("application settings are not configured")
        service = build_default_service(settings)
        request.app.state.analysis_service = service
    return service


def build_default_service(settings: Settings) -> AnalysisService:
    repository = InMemoryAnalysisJobRepository()
    runner = AnalysisAgentRunner(settings=settings, sandbox_runner=DockerSandboxRunner(settings))
    return AnalysisService(repository=repository, runner=runner)


async def require_existing_job(job_id: str, request: Request, owner_id: str) -> None:
    service = get_analysis_service(request)
    job = await service.get_job(job_id, owner_id=owner_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"job not found: {job_id}")
