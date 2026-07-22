from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_authenticated_user, get_chat_or_browser_helper_user
from app.application.browser_helper_usecases import (
    create_browser_helper_session,
    get_browser_helper_context_catalog,
)
from app.schemas.auth import UserAccount
from app.schemas.browser_helper import BrowserHelperContextCatalog, BrowserHelperSessionCreateResponse


router = APIRouter(prefix="/api/v1/browser-helper", tags=["browser-helper"])


@router.get("/context-catalog", response_model=BrowserHelperContextCatalog)
def get_browser_helper_context_catalog_endpoint(
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> BrowserHelperContextCatalog:
    return get_browser_helper_context_catalog(user_id=current_user.user_id)


@router.post(
    "/sessions",
    response_model=BrowserHelperSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_browser_helper_session_endpoint(
    request: Request,
    current_user: UserAccount = Depends(get_authenticated_user),
) -> BrowserHelperSessionCreateResponse:
    return create_browser_helper_session(
        user_id=current_user.user_id,
        user_agent=request.headers.get("user-agent"),
    )
