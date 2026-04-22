from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from maf_backend.domain.models import AnalysisJob, JobStatus


class CreateJobRequest(BaseModel):
    query: str = Field(min_length=1)
    input_files: list[str] = Field(default_factory=list)


class SandboxResultResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    artifacts: list[str]


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    query: str
    input_files: list[str]
    summary: str | None
    generated_code: str | None
    error_message: str | None
    sandbox_result: SandboxResultResponse | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: AnalysisJob) -> "JobResponse":
        sandbox_result = None
        if job.sandbox_result is not None:
            sandbox_result = SandboxResultResponse(
                stdout=job.sandbox_result.stdout,
                stderr=job.sandbox_result.stderr,
                exit_code=job.sandbox_result.exit_code,
                artifacts=job.sandbox_result.artifacts,
            )

        return cls(
            job_id=job.job_id,
            status=job.status,
            query=job.query,
            input_files=job.input_files,
            summary=job.summary,
            generated_code=job.generated_code,
            error_message=job.error_message,
            sandbox_result=sandbox_result,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
