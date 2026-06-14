from __future__ import annotations

from fastapi import APIRouter, status

from app.application.profile_session_usecases import (
    create_profile_session,
    get_profile_session,
)
from app.schemas.profile_session import ProfileSession

router = APIRouter(prefix="/api/v1/profile-sessions", tags=["v4-profile-sessions"])


@router.post("", response_model=ProfileSession, status_code=status.HTTP_201_CREATED)
def create_profile_session_endpoint() -> ProfileSession:
    return create_profile_session()


@router.get("/{session_id}", response_model=ProfileSession)
def get_profile_session_endpoint(session_id: str) -> ProfileSession:
    return get_profile_session(session_id)
