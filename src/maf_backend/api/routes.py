from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from maf_backend.api.dependencies import get_analysis_service, get_current_owner
from maf_backend.api.schemas import CreateJobRequest, JobResponse
from maf_backend.application.service import AnalysisService

router = APIRouter(prefix="/api/v1", tags=["analysis-jobs"])


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: CreateJobRequest,
    background_tasks: BackgroundTasks,
    owner_id: str = Depends(get_current_owner),
    service: AnalysisService = Depends(get_analysis_service),  # noqa: B008
) -> JobResponse:
    job = await service.create_job(owner_id=owner_id, query=payload.query, input_files=payload.input_files)
    background_tasks.add_task(service.run_job, job.job_id, owner_id=owner_id)
    return JobResponse.from_job(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    owner_id: str = Depends(get_current_owner),
    service: AnalysisService = Depends(get_analysis_service),  # noqa: B008
) -> JobResponse:
    job = await service.get_job(job_id, owner_id=owner_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"job not found: {job_id}")
    return JobResponse.from_job(job)


@router.get("/healthz", tags=["health"])
async def healthz(request: Request) -> dict[str, str]:
    return {"status": "ok", "app": request.app.title}
