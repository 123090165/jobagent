from __future__ import annotations

from fastapi import APIRouter

from app.schemas.confirmed_profile import (
    ConfirmedProfileCreateRequest,
    ConfirmedProfileCreateResponse,
    ConfirmedProfileRecordDetail,
    ConfirmedProfileRecordSummary,
)
from app.services.confirmed_profile_storage_service import (
    create_confirmed_profile_record,
    get_confirmed_profile_record,
    list_confirmed_profile_records,
)

router = APIRouter(tags=["profile"])


@router.post("/profile/confirmed", response_model=ConfirmedProfileCreateResponse)
def create_confirmed_profile(
    request: ConfirmedProfileCreateRequest,
) -> ConfirmedProfileCreateResponse:
    return create_confirmed_profile_record(request)


@router.get("/profile/confirmed", response_model=list[ConfirmedProfileRecordSummary])
def list_confirmed_profiles(limit: int = 20) -> list[ConfirmedProfileRecordSummary]:
    return list_confirmed_profile_records(limit=limit)


@router.get(
    "/profile/confirmed/{record_id}",
    response_model=ConfirmedProfileRecordDetail,
)
def get_confirmed_profile(record_id: int) -> ConfirmedProfileRecordDetail:
    return get_confirmed_profile_record(record_id)
