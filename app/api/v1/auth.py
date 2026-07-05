from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_current_user, get_required_auth_token
from app.application.auth_usecases import login_user, logout_user, register_user
from app.schemas.auth import (
    AuthLoginRequest,
    AuthMeResponse,
    AuthRegisterRequest,
    AuthTokenResponse,
    UserAccount,
)

router = APIRouter(prefix="/api/v1/auth", tags=["v4-auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register_user_endpoint(
    payload: AuthRegisterRequest,
    request: Request,
) -> AuthTokenResponse:
    return register_user(payload, user_agent=request.headers.get("user-agent"))


@router.post("/login", response_model=AuthTokenResponse)
def login_user_endpoint(
    payload: AuthLoginRequest,
    request: Request,
) -> AuthTokenResponse:
    return login_user(payload, user_agent=request.headers.get("user-agent"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user_endpoint(
    token: str = Depends(get_required_auth_token),
) -> None:
    logout_user(token)


@router.get("/me", response_model=AuthMeResponse)
def get_me_endpoint(
    current_user: UserAccount = Depends(get_current_user),
) -> AuthMeResponse:
    return AuthMeResponse(user=current_user)
