"""集中解析用户身份和 token scope，并保留仅供本地开发的匿名 local-user 兼容入口。"""

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
    """解析完整登录身份；仅在显式本地模式下允许回退到单用户账号。"""
    if credentials is None:
        # [兼容保留] 仅为本地单用户开发兜底；公网部署前应改成显式开发模式开关。
        return user_repository.ensure_local_user()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized_error()

    token_hash = hash_auth_token(credentials.credentials)
    user = auth_session_repository.get_user_for_token_hash(token_hash)
    if user is None:
        raise _unauthorized_error()
    return user


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
) -> UserAccount:
    """校验 Bearer token，并拒绝把 browser_helper 限权 token 当作完整登录会话。"""
    if credentials is None:
        raise _unauthorized_error()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized_error()
    user = auth_session_repository.get_user_for_token_hash(
        hash_auth_token(credentials.credentials)
    )
    if user is None:
        raise _unauthorized_error()
    return user


def get_chat_or_browser_helper_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
) -> UserAccount:
    """允许 Assistant 接口接收完整登录或 browser_helper 限权 token。"""
    if credentials is None:
        # [兼容保留] 旧 Side Panel 可使用 local-user；新扩展会话应使用受限 token。
        return user_repository.ensure_local_user()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized_error()
    principal = auth_session_repository.get_principal_for_token_hash(
        hash_auth_token(credentials.credentials)
    )
    if principal is None or principal.session_scope not in {"full", "browser_helper"}:
        raise _unauthorized_error()
    return principal.user


def get_required_auth_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
) -> str:
    """从 Authorization 头提取 Bearer token，缺失或格式错误时立即返回 401。"""
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
