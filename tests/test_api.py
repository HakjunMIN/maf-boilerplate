from __future__ import annotations

from fastapi.testclient import TestClient

from maf_backend.api.dependencies import get_analysis_service, get_settings
from maf_backend.domain.models import AnalysisJob, JobStatus
from maf_backend.main import app
from maf_backend.settings import Settings


class FakeService:
    def __init__(self) -> None:
        self.job = AnalysisJob(job_id="job-1", status=JobStatus.PENDING, query="hello", input_files=[])

    def create_job(self, query: str, input_files: list[str]) -> AnalysisJob:
        return AnalysisJob(job_id="job-1", status=JobStatus.PENDING, query=query, input_files=input_files)

    async def run_job(self, job_id: str) -> None:
        return None

    def get_job(self, job_id: str) -> AnalysisJob | None:
        if job_id == "job-1":
            return self.job
        return None


def test_healthz_is_public() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "MAF Analysis Backend"}


def test_jobs_require_bearer_token() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/jobs/job-1")

    assert response.status_code == 401


def test_create_job_returns_pending_response() -> None:
    fake_service = FakeService()
    app.dependency_overrides[get_settings] = lambda: Settings(api_bearer_token="secret", foundry_local_model="gpt-test")
    app.dependency_overrides[get_analysis_service] = lambda: fake_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret"},
        json={"query": "hello", "input_files": []},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["status"] == "pending"
    assert body["query"] == "hello"