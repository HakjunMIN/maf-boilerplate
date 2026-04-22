from __future__ import annotations

from dataclasses import replace
from typing import Protocol
from uuid import uuid4

from maf_backend.domain.models import AgentExecutionResult, AnalysisJob, JobStatus
from maf_backend.domain.repositories import AnalysisJobRepository


class AnalysisRunner(Protocol):
    async def run(self, query: str, input_files: list[str]) -> AgentExecutionResult:
        ...


class AnalysisService:
    def __init__(self, repository: AnalysisJobRepository, runner: AnalysisRunner) -> None:
        self._repository = repository
        self._runner = runner

    def create_job(self, query: str, input_files: list[str]) -> AnalysisJob:
        job = AnalysisJob(
            job_id=uuid4().hex,
            status=JobStatus.PENDING,
            query=query,
            input_files=list(input_files),
        )
        self._repository.create(job)
        return job

    def get_job(self, job_id: str) -> AnalysisJob | None:
        return self._repository.get(job_id)

    async def run_job(self, job_id: str) -> None:
        job = self._repository.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")

        running_job = replace(job, status=JobStatus.RUNNING, error_message=None)
        self._repository.save(running_job)

        try:
            result = await self._runner.run(running_job.query, running_job.input_files)
        except Exception as exc:
            failed_job = replace(running_job, status=JobStatus.FAILED, error_message=str(exc))
            self._repository.save(failed_job)
            return

        completed_job = replace(
            running_job,
            status=JobStatus.COMPLETED,
            summary=result.summary,
            generated_code=result.generated_code,
            sandbox_result=result.sandbox_result,
            web_search_results=list(result.web_search_results),
            error_message=None,
        )
        self._repository.save(completed_job)