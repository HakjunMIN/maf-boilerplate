from __future__ import annotations

from functools import lru_cache

from maf_backend.application.agent import AnalysisAgentRunner
from maf_backend.application.service import AnalysisService
from maf_backend.domain.repositories import AnalysisJobRepository
from maf_backend.infrastructure.repository import InMemoryAnalysisJobRepository
from maf_backend.infrastructure.sandbox.runner import DockerSandboxRunner
from maf_backend.settings import Settings


_job_repository = InMemoryAnalysisJobRepository()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_job_repository() -> AnalysisJobRepository:
    return _job_repository


def get_sandbox_runner() -> DockerSandboxRunner:
    return DockerSandboxRunner(get_settings())


def get_analysis_runner() -> AnalysisAgentRunner:
    return AnalysisAgentRunner(get_settings(), get_sandbox_runner())


def get_analysis_service() -> AnalysisService:
    return AnalysisService(get_job_repository(), get_analysis_runner())