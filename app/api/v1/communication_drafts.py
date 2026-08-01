from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_or_browser_helper_user
from app.application.communication_usecases import (
    confirm_greeting_sent,
    update_communication_draft,
)
from app.schemas.auth import UserAccount
from app.schemas.communication import (
    CommunicationDraft,
    CommunicationDraftUpdateRequest,
    CommunicationSentConfirmation,
    CommunicationSentResult,
)

router = APIRouter(prefix="/api/v1/communication-drafts", tags=["v4-communication"])


@router.patch("/{draft_id}", response_model=CommunicationDraft)
def update_communication_draft_endpoint(
    draft_id: str,
    payload: CommunicationDraftUpdateRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> CommunicationDraft:
    return update_communication_draft(
        draft_id,
        payload,
        user_id=current_user.user_id,
    )


@router.post("/{draft_id}/confirm-sent", response_model=CommunicationSentResult)
def confirm_greeting_sent_endpoint(
    draft_id: str,
    payload: CommunicationSentConfirmation,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> CommunicationSentResult:
    return confirm_greeting_sent(
        draft_id,
        payload,
        user_id=current_user.user_id,
    )
