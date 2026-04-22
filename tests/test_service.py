from __future__ import annotations

import pytest

from maf_backend.application.service import AnalysisService
from maf_backend.domain.models import AgentExecutionResult, JobStatus
from maf_backend.infrastructure.repository import InMemoryAnalysisJobRepository


class FakeRunner:
    async def run(self, query: str, input_files: list[str]) -> AgentExecutionResult:
        return AgentExecutionResult(summary="done", web_search_results=["doc snippet"])


@pytest.mark.asyncio
async def test_service_completes_job_without_sandbox_result() -> None:
    repository = InMemoryAnalysisJobRepository()
    service = AnalysisService(repository, FakeRunner())

    job = service.create_job("find docs", [])
    await service.run_job(job.job_id)
    stored = service.get_job(job.job_id)

    assert stored is not None
    assert stored.status == JobStatus.COMPLETED
    assert stored.summary == "done"
    assert stored.sandbox_result is None
    assert stored.web_search_results == ["doc snippet"]