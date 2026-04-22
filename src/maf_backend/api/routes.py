from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from maf_backend.api.dependencies import get_analysis_service, get_settings
from maf_backend.api.schemas import JobCreateRequest, JobResponse
from maf_backend.application.service import AnalysisService
from maf_backend.infrastructure.auth import verify_bearer_token
from maf_backend.settings import Settings


router = APIRouter(prefix="/api/v1")


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "app": "MAF Analysis Backend"}


@router.post("/jobs", response_model=JobResponse)
async def create_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    service: AnalysisService = Depends(get_analysis_service),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    await verify_bearer_token(authorization=authorization, settings=settings)
    job = service.create_job(payload.query, payload.input_files)
    background_tasks.add_task(service.run_job, job.job_id)
    return JobResponse.from_job(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    service: AnalysisService = Depends(get_analysis_service),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    await verify_bearer_token(authorization=authorization, settings=settings)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
    return JobResponse.from_job(job)