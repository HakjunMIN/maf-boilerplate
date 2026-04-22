from __future__ import annotations

import asyncio

from maf_backend.domain.models import AnalysisJob


class InMemoryAnalysisJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: AnalysisJob) -> AnalysisJob:
        async with self._lock:
            self._jobs[job.job_id] = job
            return job

    async def get(self, job_id: str) -> AnalysisJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job: AnalysisJob) -> AnalysisJob:
        async with self._lock:
            self._jobs[job.job_id] = job
            return job
