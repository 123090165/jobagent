"""编排 认证账户与会话 的所有权检查、状态转换、领域服务和持久化操作。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from app.repositories.auth_session_repository import (
    AuthSessionRepository,
    auth_session_repository,
)
from app.repositories.user_repository import (
    DuplicateUsernameError,
    UserRepository,
    user_repository,
)
from app.schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    UserAccount,
)
from app.services.errors import JobAgentError
from app.services.password_service import (
    generate_auth_token,
    hash_auth_token,
    hash_password,
    verify_password,
)

DEFAULT_AUTH_SESSION_HOURS = 24 * 14


def register_user(
    payload: AuthRegisterRequest,
    *,
    user_agent: str | None = None,
    users: UserRepository = user_repository,
    sessions: AuthSessionRepository = auth_session_repository,
) -> AuthTokenResponse:
    """创建账户并立即签发登录会话；用户名冲突会转换为稳定的 API 错误。"""
    password_hash, password_salt, password_algorithm = hash_password(payload.password)
    try:
        user = users.create(
            username=payload.username,
            password_hash=password_hash,
            password_salt=password_salt,
            password_algorithm=password_algorithm,
            display_name=payload.display_name,
        )
    except DuplicateUsernameError as exc:
        raise JobAgentError(
            message="Username is already registered.",
            error_code="username_already_registered",
            status_code=409,
        ) from exc
    return _create_token_response(user, user_agent=user_agent, sessions=sessions)


def login_user(
    payload: AuthLoginRequest,
    *,
    user_agent: str | None = None,
    users: UserRepository = user_repository,
    sessions: AuthSessionRepository = auth_session_repository,
) -> AuthTokenResponse:
    """校验密码后签发 bearer token；数据库只保存 token 哈希。"""
    record = users.get_with_password(payload.username)
    if record is None:
        raise _invalid_credentials_error()

    user = record["user"]
    if not isinstance(user, UserAccount) or user.disabled_at is not None:
        raise _invalid_credentials_error()

    is_valid = verify_password(
        payload.password,
        password_hash=str(record["password_hash"]),
        password_salt=str(record["password_salt"]),
        password_algorithm=str(record["password_algorithm"]),
    )
    if not is_valid:
        raise _invalid_credentials_error()

    return _create_token_response(user, user_agent=user_agent, sessions=sessions)


def logout_user(
    token: str,
    *,
    sessions: AuthSessionRepository = auth_session_repository,
) -> None:
    """撤销当前 token 对应的服务端会话；重复退出保持幂等。"""
    sessions.revoke_token_hash(hash_auth_token(token))


def _create_token_response(
    user: UserAccount,
    *,
    user_agent: str | None,
    sessions: AuthSessionRepository,
) -> AuthTokenResponse:
    token = generate_auth_token()
    expires_at = _utc_now() + timedelta(hours=_auth_session_hours())
    sessions.create(
        user_id=user.user_id,
        token_hash=hash_auth_token(token),
        expires_at=expires_at,
        user_agent=user_agent,
    )
    return AuthTokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=user,
    )


def _auth_session_hours() -> int:
    raw_value = os.getenv("JOBAGENT_AUTH_SESSION_HOURS", "").strip()
    if not raw_value:
        return DEFAULT_AUTH_SESSION_HOURS
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_AUTH_SESSION_HOURS
    return max(1, parsed)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _invalid_credentials_error() -> JobAgentError:
    return JobAgentError(
        message="Invalid username or password.",
        error_code="invalid_credentials",
        status_code=401,
    )
