from __future__ import annotations

from typing import Protocol

from maf_backend.domain.models import AnalysisJob


class AnalysisJobRepository(Protocol):
    def create(self, job: AnalysisJob) -> None:
        ...

    def get(self, job_id: str) -> AnalysisJob | None:
        ...

    def save(self, job: AnalysisJob) -> None:
        ...