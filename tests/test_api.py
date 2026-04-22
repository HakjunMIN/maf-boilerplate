from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi.testclient import TestClient

os.environ.setdefault("API_BEARER_TOKEN", "secret")

from maf_backend.main import create_app
from maf_backend.settings import Settings


@dataclass(frozen=True)
class FakeSandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    artifacts: list[str]


@dataclass(frozen=True)
class FakeAgentResult:
    summary: str
    generated_code: str
    sandbox_result: FakeSandboxResult


class FakeService:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}

    async def create_job(self, *, owner_id: str, query: str, input_files: list[str]):
        job = {
            "job_id": "job-1",
            "status": "pending",
            "query": query,
            "input_files": input_files,
            "summary": None,
            "generated_code": None,
            "error_message": None,
            "sandbox_result": None,
            "created_at": "2026-04-22T00:00:00Z",
            "updated_at": "2026-04-22T00:00:00Z",
        }
        self.jobs[job["job_id"]] = job
        return type("Job", (), job)

    async def run_job(self, job_id: str, *, owner_id: str):
        return None

    async def get_job(self, job_id: str, *, owner_id: str):
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return type("Job", (), job)


def test_healthz_is_public() -> None:
    settings = Settings(API_BEARER_TOKEN="secret")
    app = create_app(settings=settings, service=FakeService())
    client = TestClient(app)

    response = client.get("/api/v1/healthz")

    assert response.status_code == 200


def test_jobs_require_bearer_token() -> None:
    settings = Settings(API_BEARER_TOKEN="secret")
    app = create_app(settings=settings, service=FakeService())
    client = TestClient(app)

    response = client.get("/api/v1/jobs/job-1")

    assert response.status_code == 401


def test_create_job_accepts_valid_token() -> None:
    settings = Settings(API_BEARER_TOKEN="secret")
    app = create_app(settings=settings, service=FakeService())
    client = TestClient(app)

    response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret"},
        json={"query": "analyze sales", "input_files": []},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-1"
