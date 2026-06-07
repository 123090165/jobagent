from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationRecordResponse,
    ApplicationUpdateRequest,
    ApplicationStatus,
)
from app.schemas.api import ApplicationAnalyzeRequest, ApplicationAnalyzeResponse
from app.services.application_service import (
    analyze_application,
    list_applications,
    load_application,
    save_application,
    update_application,
)

router = APIRouter(tags=["applications"])


@router.get("/applications", response_model=list[ApplicationRecordResponse])
def list_application_records(
    limit: int = 20,
    status: ApplicationStatus | None = None,
    keyword: str | None = None,
) -> list[ApplicationRecordResponse]:
    records = list_applications(limit=limit, status=status, keyword=keyword)
    return [ApplicationRecordResponse.model_validate(record) for record in records]


@router.post("/applications", response_model=ApplicationRecordResponse)
def create_or_update_application(request: ApplicationCreateRequest) -> ApplicationRecordResponse:
    record = save_application(
        job_id=request.job_id,
        status=request.status,
        notes=request.notes,
        next_action=request.next_action,
        resume_version_id=request.resume_version_id,
        resume_version_label=request.resume_version_label,
    )
    if record is None:
        detail = "job or resume version not found" if request.resume_version_id is not None else "job not found"
        raise HTTPException(status_code=404, detail=detail)
    return ApplicationRecordResponse.model_validate(record)


@router.get("/applications/{application_id}", response_model=ApplicationRecordResponse)
def get_application(application_id: int) -> ApplicationRecordResponse:
    record = load_application(application_id)
    if record is None:
        raise HTTPException(status_code=404, detail="application not found")
    return ApplicationRecordResponse.model_validate(record)


@router.patch("/applications/{application_id}", response_model=ApplicationRecordResponse)
def patch_application(
    application_id: int,
    request: ApplicationUpdateRequest,
) -> ApplicationRecordResponse:
    record = update_application(
        application_id=application_id,
        status=request.status,
        notes=request.notes,
        next_action=request.next_action,
        resume_version_id=request.resume_version_id,
        resume_version_label=request.resume_version_label,
    )
    if record is None:
        detail = (
            "application or resume version not found"
            if request.resume_version_id is not None
            else "application not found"
        )
        raise HTTPException(status_code=404, detail=detail)
    return ApplicationRecordResponse.model_validate(record)


@router.post(
    "/applications/{application_id}/analyze",
    response_model=ApplicationAnalyzeResponse,
)
def analyze_application_record(
    application_id: int,
    request: ApplicationAnalyzeRequest,
) -> ApplicationAnalyzeResponse:
    result = analyze_application(
        application_id,
        resume_text=request.resume_text,
        resume_version_id=request.resume_version_id,
        mode=request.mode,
    )
    return ApplicationAnalyzeResponse.model_validate(result)
