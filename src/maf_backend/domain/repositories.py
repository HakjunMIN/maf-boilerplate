from __future__ import annotations

from typing import Protocol

from maf_backend.domain.models import AnalysisJob


class AnalysisJobRepository(Protocol):
    async def create(self, job: AnalysisJob) -> AnalysisJob: ...

    async def get(self, job_id: str) -> AnalysisJob | None: ...

    async def update(self, job: AnalysisJob) -> AnalysisJob: ...
