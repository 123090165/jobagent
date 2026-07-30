"""读写 SQLite 中的用户账户，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.auth import UserAccount
from app.storage.database import LOCAL_USER_ID, get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DuplicateUsernameError(ValueError):
    """表示 DuplicateUsernameError 对应的可识别失败。"""
    pass


class UserRepository:
    """封装用户的 SQLite 读写与模型重建。"""
    def create(
        self,
        *,
        username: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        display_name: str | None = None,
    ) -> UserAccount:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        now = _utc_now()
        user = UserAccount(
            user_id=str(uuid4()),
            username=username,
            display_name=display_name,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            try:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id,
                        username,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        display_name,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.user_id,
                        user.username,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        user.display_name,
                        user.created_at.isoformat(),
                        user.updated_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateUsernameError(username) from exc
            connection.commit()
        return user

    def get(self, user_id: str) -> UserAccount | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    user_id,
                    username,
                    display_name,
                    created_at,
                    updated_at,
                    disabled_at
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def list_all(self, *, include_disabled: bool = False) -> list[UserAccount]:
        """按方法参数限定的主键或用户范围列出all。"""
        where_clause = "" if include_disabled else "WHERE disabled_at IS NULL"
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                f"""
                SELECT
                    user_id,
                    username,
                    display_name,
                    created_at,
                    updated_at,
                    disabled_at
                FROM users
                {where_clause}
                ORDER BY created_at, user_id
                """
            ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_with_password(self, username: str) -> dict[str, object] | None:
        """按方法参数限定的主键或用户范围获取withpassword。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    user_id,
                    username,
                    password_hash,
                    password_salt,
                    password_algorithm,
                    display_name,
                    created_at,
                    updated_at,
                    disabled_at
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None:
            return None
        return {
            "user": self._row_to_user(row),
            "password_hash": row["password_hash"],
            "password_salt": row["password_salt"],
            "password_algorithm": row["password_algorithm"],
        }

    def ensure_local_user(self) -> UserAccount:
        """按方法参数限定的主键或用户范围确保存在local用户。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    user_id,
                    username,
                    display_name,
                    created_at,
                    updated_at,
                    disabled_at
                FROM users
                WHERE user_id = ?
                """,
                (LOCAL_USER_ID,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Local user was not initialized.")
        return self._row_to_user(row)

    @staticmethod
    def _row_to_user(row: object) -> UserAccount:
        return UserAccount(
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


user_repository = UserRepository()
