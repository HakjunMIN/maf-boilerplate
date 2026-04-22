from __future__ import annotations

from dataclasses import dataclass

import pytest

from maf_backend.application.service import AnalysisService
from maf_backend.domain.models import JobStatus, SandboxExecutionResult
from maf_backend.infrastructure.repository import InMemoryAnalysisJobRepository


@dataclass(frozen=True)
class FakeRunnerResult:
    summary: str
    generated_code: str
    sandbox_result: SandboxExecutionResult


class FakeRunner:
    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code

    async def run(self, query: str, input_files: list[str]) -> FakeRunnerResult:
        return FakeRunnerResult(
            summary=f"summary for {query}",
            generated_code="print('ok')",
            sandbox_result=SandboxExecutionResult(
                stdout="ok",
                stderr="" if self.exit_code == 0 else "boom",
                exit_code=self.exit_code,
                artifacts=[],
            ),
        )


@pytest.mark.asyncio
async def test_run_job_marks_completed() -> None:
    repository = InMemoryAnalysisJobRepository()
    service = AnalysisService(repository=repository, runner=FakeRunner())

    job = await service.create_job(owner_id="local-user", query="sum values", input_files=[])
    result = await service.run_job(job.job_id, owner_id="local-user")

    assert result.status == JobStatus.completed
    assert result.summary == "summary for sum values"
    assert result.generated_code == "print('ok')"


@pytest.mark.asyncio
async def test_run_job_marks_failed_when_sandbox_fails() -> None:
    repository = InMemoryAnalysisJobRepository()
    service = AnalysisService(repository=repository, runner=FakeRunner(exit_code=1))

    job = await service.create_job(owner_id="local-user", query="explode", input_files=[])
    result = await service.run_job(job.job_id, owner_id="local-user")

    assert result.status == JobStatus.failed
    assert result.error_message == "boom"
