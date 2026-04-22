from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from maf_backend.domain.models import AnalysisJob
from maf_backend.domain.repositories import AnalysisJobRepository


class AnalysisRunner(Protocol):
    async def run(self, query: str, input_files: list[str]): ...


class AnalysisService:
    def __init__(self, repository: AnalysisJobRepository, runner: AnalysisRunner) -> None:
        self._repository = repository
        self._runner = runner

    async def create_job(self, *, owner_id: str, query: str, input_files: list[str]) -> AnalysisJob:
        job = AnalysisJob(job_id=uuid4().hex, owner_id=owner_id, query=query, input_files=input_files)
        return await self._repository.create(job)

    async def get_job(self, job_id: str, *, owner_id: str) -> AnalysisJob | None:
        job = await self._repository.get(job_id)
        if job is None or job.owner_id != owner_id:
            return None
        return job

    async def run_job(self, job_id: str, *, owner_id: str) -> AnalysisJob:
        job = await self.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise KeyError(job_id)

        job.mark_running()
        await self._repository.update(job)

        try:
            result = await self._runner.run(job.query, job.input_files)
        except Exception as exc:
            job.mark_failed(generated_code=None, error_message=str(exc), sandbox_result=None)
            return await self._repository.update(job)

        if result.sandbox_result.exit_code != 0:
            message = result.sandbox_result.stderr or "sandbox execution failed"
            job.mark_failed(
                generated_code=result.generated_code,
                error_message=message,
                sandbox_result=result.sandbox_result,
            )
        else:
            job.mark_completed(
                summary=result.summary,
                generated_code=result.generated_code,
                sandbox_result=result.sandbox_result,
            )
        return await self._repository.update(job)
