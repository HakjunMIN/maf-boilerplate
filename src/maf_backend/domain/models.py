from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class SandboxExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    artifacts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentExecutionResult:
    summary: str
    generated_code: str = ""
    sandbox_result: SandboxExecutionResult | None = None
    web_search_results: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisJob:
    job_id: str
    status: JobStatus
    query: str
    input_files: list[str] = field(default_factory=list)
    summary: str | None = None
    generated_code: str = ""
    sandbox_result: SandboxExecutionResult | None = None
    web_search_results: list[str] = field(default_factory=list)
    error_message: str | None = None