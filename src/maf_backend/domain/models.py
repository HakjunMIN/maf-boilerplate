from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


@dataclass(frozen=True)
class SandboxExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    artifacts: list[str]


@dataclass
class AnalysisJob:
    job_id: str
    owner_id: str
    query: str
    input_files: list[str]
    status: JobStatus = JobStatus.pending
    summary: str | None = None
    generated_code: str | None = None
    sandbox_result: SandboxExecutionResult | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def mark_running(self) -> None:
        self.status = JobStatus.running
        self.updated_at = utcnow()

    def mark_completed(self, *, summary: str, generated_code: str, sandbox_result: SandboxExecutionResult) -> None:
        self.status = JobStatus.completed
        self.summary = summary
        self.generated_code = generated_code
        self.sandbox_result = sandbox_result
        self.error_message = None
        self.updated_at = utcnow()

    def mark_failed(
        self,
        *,
        generated_code: str | None,
        error_message: str,
        sandbox_result: SandboxExecutionResult | None,
    ) -> None:
        self.status = JobStatus.failed
        self.generated_code = generated_code
        self.error_message = error_message
        self.sandbox_result = sandbox_result
        self.updated_at = utcnow()
