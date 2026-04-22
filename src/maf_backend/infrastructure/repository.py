from __future__ import annotations

from threading import Lock

from maf_backend.domain.models import AnalysisJob


class InMemoryAnalysisJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = Lock()

    def create(self, job: AnalysisJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get(self, job_id: str) -> AnalysisJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def save(self, job: AnalysisJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job