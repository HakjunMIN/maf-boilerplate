from __future__ import annotations

from pydantic import BaseModel, Field

from maf_backend.domain.models import AnalysisJob, SandboxExecutionResult


class JobCreateRequest(BaseModel):
    query: str = Field(min_length=1)
    input_files: list[str] = Field(default_factory=list)


class SandboxResultResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    artifacts: list[str] = Field(default_factory=list)

    @classmethod
    def from_result(cls, result: SandboxExecutionResult) -> "SandboxResultResponse":
        return cls(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            artifacts=list(result.artifacts),
        )


class JobResponse(BaseModel):
    job_id: str
    status: str
    query: str
    input_files: list[str] = Field(default_factory=list)
    summary: str | None = None
    generated_code: str = ""
    sandbox_result: SandboxResultResponse | None = None
    web_search_results: list[str] = Field(default_factory=list)
    error_message: str | None = None

    @classmethod
    def from_job(cls, job: AnalysisJob) -> "JobResponse":
        return cls(
            job_id=job.job_id,
            status=job.status.value,
            query=job.query,
            input_files=list(job.input_files),
            summary=job.summary,
            generated_code=job.generated_code,
            sandbox_result=(
                SandboxResultResponse.from_result(job.sandbox_result)
                if job.sandbox_result is not None
                else None
            ),
            web_search_results=list(job.web_search_results),
            error_message=job.error_message,
        )