from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.application.confirmed_profile_usecases import get_confirmed_profile
from app.schemas.auth import UserAccount
from app.schemas.confirmed_profile import ConfirmedProfileResponse

router = APIRouter(prefix="/api/v1/confirmed-profiles", tags=["v4-confirmed-profiles"])


@router.get("/{confirmed_profile_id}", response_model=ConfirmedProfileResponse)
def get_confirmed_profile_endpoint(
    confirmed_profile_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ConfirmedProfileResponse:
    return get_confirmed_profile(confirmed_profile_id, user_id=current_user.user_id)
