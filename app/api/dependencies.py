from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories.auth_session_repository import auth_session_repository
from app.repositories.user_repository import user_repository
from app.schemas.auth import UserAccount
from app.services.errors import JobAgentError
from app.services.password_service import hash_auth_token

bearer_auth = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
) -> UserAccount:
    if credentials is None:
        return user_repository.ensure_local_user()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized_error()

    token_hash = hash_auth_token(credentials.credentials)
    user = auth_session_repository.get_user_for_token_hash(token_hash)
    if user is None:
        raise _unauthorized_error()
    return user


def get_required_auth_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
) -> str:
    if credentials is None:
        raise _unauthorized_error()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized_error()
    return credentials.credentials


def _unauthorized_error() -> JobAgentError:
    return JobAgentError(
        message="Authentication is required.",
        error_code="unauthorized",
        status_code=401,
    )
