"""读写 SQLite 中的认证账户与会话，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.auth import UserAccount
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AuthSessionPrincipal:
    user: UserAccount
    session_scope: str


class AuthSessionRepository:
    """封装认证会话的 SQLite 读写与模型重建。"""
    def create(
        self,
        *,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        session_scope: str = "full",
    ) -> str:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        auth_session_id = str(uuid4())
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    auth_session_id,
                    user_id,
                    token_hash,
                    created_at,
                    expires_at,
                    revoked_at,
                    user_agent,
                    session_scope
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    auth_session_id,
                    user_id,
                    token_hash,
                    now.isoformat(),
                    expires_at.isoformat(),
                    user_agent,
                    session_scope,
                ),
            )
            connection.commit()
        return auth_session_id

    def get_user_for_token_hash(self, token_hash: str) -> UserAccount | None:
        """按方法参数限定的主键或用户范围获取用户for令牌hash。"""
        principal = self.get_principal_for_token_hash(token_hash)
        if principal is None or principal.session_scope != "full":
            return None
        return principal.user

    def get_principal_for_token_hash(self, token_hash: str) -> AuthSessionPrincipal | None:
        """按方法参数限定的主键或用户范围获取principalfor令牌hash。"""
        now = _utc_now().isoformat()
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    users.user_id,
                    users.username,
                    users.display_name,
                    users.created_at,
                    users.updated_at,
                    users.disabled_at,
                    auth_sessions.session_scope
                FROM auth_sessions
                JOIN users ON users.user_id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = ?
                    AND auth_sessions.revoked_at IS NULL
                    AND auth_sessions.expires_at > ?
                    AND users.disabled_at IS NULL
                """,
                (token_hash, now),
            ).fetchone()
        if row is None:
            return None
        user = UserAccount(
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            disabled_at=(
                datetime.fromisoformat(row["disabled_at"])
                if row["disabled_at"] is not None
                else None
            ),
        )
        return AuthSessionPrincipal(user=user, session_scope=row["session_scope"])

    def revoke_token_hash(self, token_hash: str) -> None:
        """按方法参数限定的主键或用户范围撤销令牌hash。"""
        now = _utc_now().isoformat()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = ?
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (now, token_hash),
            )
            connection.commit()

    def revoke_all_for_user(self, user_id: str) -> None:
        """按方法参数限定的主键或用户范围撤销allfor用户。"""
        now = _utc_now().isoformat()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = ?
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (now, user_id),
            )
            connection.commit()


auth_session_repository = AuthSessionRepository()
