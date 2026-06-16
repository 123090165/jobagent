from __future__ import annotations

from fastapi import APIRouter

from app.application.confirmed_profile_usecases import confirm_profile_draft
from app.application.profile_draft_usecases import (
    get_profile_draft,
    update_profile_draft,
)
from app.schemas.confirmed_profile import ConfirmedProfileResponse
from app.schemas.profile_draft import ProfileDraftResponse, UpdateProfileDraftRequest

router = APIRouter(prefix="/api/v1/profile-drafts", tags=["v4-profile-drafts"])


@router.get("/{draft_id}", response_model=ProfileDraftResponse)
def get_profile_draft_endpoint(draft_id: str) -> ProfileDraftResponse:
    return get_profile_draft(draft_id)


@router.patch("/{draft_id}", response_model=ProfileDraftResponse)
def update_profile_draft_endpoint(
    draft_id: str,
    payload: UpdateProfileDraftRequest,
) -> ProfileDraftResponse:
    return update_profile_draft(draft_id, payload)


@router.post("/{draft_id}/confirm", response_model=ConfirmedProfileResponse)
def confirm_profile_draft_endpoint(draft_id: str) -> ConfirmedProfileResponse:
    return confirm_profile_draft(draft_id)
