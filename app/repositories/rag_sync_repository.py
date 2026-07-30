"""读写 SQLite 中的RAG 同步事件与资源状态，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.rag_sync import (
    RAGIndexEvent,
    RAGResourceStatus,
    RAGResourceType,
    RAGSyncOverview,
    RAGSyncOperation,
)
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def rag_sync_enabled() -> bool:
    """按方法参数限定的主键或用户范围处理知识库同步enabled。"""
    return os.getenv("JOBAGENT_RAG_SYNC_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class RAGSyncRepository:
    """封装rag同步的 SQLite 读写与模型重建。"""
    def enqueue_if_enabled(
        self,
        *,
        user_id: str,
        resource_type: RAGResourceType,
        resource_id: str,
        operation: RAGSyncOperation,
        connection: sqlite3.Connection | None = None,
    ) -> RAGIndexEvent | None:
        """按方法参数限定的主键或用户范围处理enqueueifenabled。"""
        if not rag_sync_enabled():
            return None
        return self.enqueue(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            operation=operation,
            connection=connection,
        )

    def enqueue(
        self,
        *,
        user_id: str,
        resource_type: RAGResourceType,
        resource_id: str,
        operation: RAGSyncOperation,
        connection: sqlite3.Connection | None = None,
    ) -> RAGIndexEvent:
        """按方法参数限定的主键或用户范围处理enqueue。"""
        if connection is None:
            with get_connection() as owned_connection:
                init_database(owned_connection)
                event = self._enqueue(
                    owned_connection,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    operation=operation,
                )
                owned_connection.commit()
                return event
        return self._enqueue(
            connection,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            operation=operation,
        )

    def _enqueue(
        self,
        connection: sqlite3.Connection,
        *,
        user_id: str,
        resource_type: RAGResourceType,
        resource_id: str,
        operation: RAGSyncOperation,
    ) -> RAGIndexEvent:
        now = _utc_now()
        row = connection.execute(
            """
            SELECT desired_version
            FROM rag_resource_status
            WHERE user_id = ? AND resource_type = ? AND resource_id = ?
            """,
            (user_id, resource_type, resource_id),
        ).fetchone()
        version = int(row["desired_version"]) + 1 if row is not None else 1
        event_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO rag_index_outbox (
                event_id, user_id, resource_type, resource_id, resource_version,
                operation, status, attempt_count, available_at,
                last_error_code, last_error_message, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, NULL, NULL, ?, NULL)
            """,
            (
                event_id,
                user_id,
                resource_type,
                resource_id,
                version,
                operation,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO rag_resource_status (
                user_id, resource_type, resource_id, desired_version,
                indexed_version, indexed_document_id, sync_status,
                last_event_id, last_synced_at, last_error_code, updated_at
            ) VALUES (?, ?, ?, ?, NULL, NULL, 'pending', ?, NULL, NULL, ?)
            ON CONFLICT(user_id, resource_type, resource_id) DO UPDATE SET
                desired_version = excluded.desired_version,
                sync_status = 'pending',
                last_event_id = excluded.last_event_id,
                last_error_code = NULL,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                resource_type,
                resource_id,
                version,
                event_id,
                now.isoformat(),
            ),
        )
        return self.get_event(event_id, connection=connection)

    def claim_pending(
        self,
        *,
        limit: int = 10,
        max_attempts: int = 8,
        lease_seconds: int = 300,
    ) -> list[RAGIndexEvent]:
        """按方法参数限定的主键或用户范围领取pending。"""
        bounded_limit = max(1, min(100, int(limit)))
        bounded_attempts = max(1, min(100, int(max_attempts)))
        now_value = _utc_now()
        now = now_value.isoformat()
        lease_until = (
            now_value + timedelta(seconds=max(10, min(3_600, int(lease_seconds))))
        ).isoformat()
        with get_connection() as connection:
            init_database(connection)
            connection.execute("BEGIN IMMEDIATE")
            expired_terminal_ids = [
                str(row["event_id"])
                for row in connection.execute(
                    """
                    SELECT event_id
                    FROM rag_index_outbox
                    WHERE status = 'processing'
                      AND available_at <= ?
                      AND attempt_count >= ?
                    """,
                    (now, bounded_attempts),
                ).fetchall()
            ]
            if expired_terminal_ids:
                placeholders = ",".join("?" for _ in expired_terminal_ids)
                connection.execute(
                    f"""
                    UPDATE rag_resource_status
                    SET sync_status = 'failed',
                        last_error_code = 'WORKER_LEASE_EXPIRED',
                        updated_at = ?
                    WHERE last_event_id IN ({placeholders})
                    """,
                    [now, *expired_terminal_ids],
                )
                connection.execute(
                    f"""
                    UPDATE rag_index_outbox
                    SET status = 'failed',
                        last_error_code = 'WORKER_LEASE_EXPIRED',
                        last_error_message = 'Worker lease expired after maximum attempts'
                    WHERE event_id IN ({placeholders})
                    """,
                    expired_terminal_ids,
                )
            rows = connection.execute(
                """
                SELECT event_id
                FROM rag_index_outbox
                WHERE status IN ('pending', 'failed', 'processing')
                  AND available_at <= ?
                  AND attempt_count < ?
                ORDER BY created_at
                LIMIT ?
                """,
                (now, bounded_attempts, bounded_limit),
            ).fetchall()
            event_ids = [str(row["event_id"]) for row in rows]
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                connection.execute(
                    f"""
                    UPDATE rag_index_outbox
                    SET status = 'processing', attempt_count = attempt_count + 1,
                        available_at = ?
                    WHERE event_id IN ({placeholders})
                    """,
                    [lease_until, *event_ids],
                )
            connection.commit()
            return [
                self.get_event(event_id, connection=connection)
                for event_id in event_ids
            ]

    def mark_completed(
        self,
        *,
        event_id: str,
        document_id: str | None,
    ) -> None:
        """按方法参数限定的主键或用户范围标记completed。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            event = self.get_event(event_id, connection=connection)
            connection.execute(
                """
                UPDATE rag_index_outbox
                SET status = 'completed', completed_at = ?,
                    last_error_code = NULL, last_error_message = NULL
                WHERE event_id = ?
                """,
                (now.isoformat(), event_id),
            )
            if event.operation == "delete":
                indexed_version = None
                indexed_document_id = None
                sync_status = "deleted"
            else:
                indexed_version = event.resource_version
                indexed_document_id = document_id
                sync_status = "ready"
            connection.execute(
                """
                UPDATE rag_resource_status
                SET indexed_version = ?, indexed_document_id = ?,
                    sync_status = ?, last_synced_at = ?,
                    last_error_code = NULL, updated_at = ?
                WHERE user_id = ? AND resource_type = ? AND resource_id = ?
                  AND last_event_id = ?
                """,
                (
                    indexed_version,
                    indexed_document_id,
                    sync_status,
                    now.isoformat(),
                    now.isoformat(),
                    event.user_id,
                    event.resource_type,
                    event.resource_id,
                    event_id,
                ),
            )
            connection.commit()

    def mark_failed(
        self,
        *,
        event_id: str,
        error_code: str,
        error_message: str,
        retry_delay_seconds: int = 30,
    ) -> None:
        """按方法参数限定的主键或用户范围标记failed。"""
        now = _utc_now()
        available_at = now + timedelta(seconds=max(1, retry_delay_seconds))
        bounded_message = error_message[:1_000]
        with get_connection() as connection:
            init_database(connection)
            event = self.get_event(event_id, connection=connection)
            connection.execute(
                """
                UPDATE rag_index_outbox
                SET status = 'failed', available_at = ?,
                    last_error_code = ?, last_error_message = ?
                WHERE event_id = ?
                """,
                (available_at.isoformat(), error_code, bounded_message, event_id),
            )
            connection.execute(
                """
                UPDATE rag_resource_status
                SET sync_status = 'failed', last_error_code = ?, updated_at = ?
                WHERE user_id = ? AND resource_type = ? AND resource_id = ?
                  AND last_event_id = ?
                """,
                (
                    error_code,
                    now.isoformat(),
                    event.user_id,
                    event.resource_type,
                    event.resource_id,
                    event_id,
                ),
            )
            connection.commit()

    def get_event(
        self,
        event_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> RAGIndexEvent:
        """按方法参数限定的主键或用户范围获取事件。"""
        if connection is None:
            with get_connection() as owned_connection:
                init_database(owned_connection)
                return self.get_event(event_id, connection=owned_connection)
        row = connection.execute(
            "SELECT * FROM rag_index_outbox WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"RAG sync event not found: {event_id}")
        return _event_from_row(row)

    def get_status(
        self,
        *,
        user_id: str,
        resource_type: RAGResourceType,
        resource_id: str,
    ) -> RAGResourceStatus | None:
        """按方法参数限定的主键或用户范围获取状态。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT * FROM rag_resource_status
                WHERE user_id = ? AND resource_type = ? AND resource_id = ?
                """,
                (user_id, resource_type, resource_id),
            ).fetchone()
        return _status_from_row(row) if row is not None else None

    def get_overview(
        self,
        *,
        user_id: str | None = None,
        recent_failure_limit: int = 10,
    ) -> RAGSyncOverview:
        """按方法参数限定的主键或用户范围获取overview。"""
        bounded_limit = max(1, min(100, int(recent_failure_limit)))
        resource_filter = "WHERE user_id = ?" if user_id else ""
        event_filter = "WHERE user_id = ?" if user_id else ""
        parameters: tuple[object, ...] = (user_id,) if user_id else ()
        with get_connection() as connection:
            init_database(connection)
            resource_rows = connection.execute(
                f"""
                SELECT sync_status, COUNT(*) AS count
                FROM rag_resource_status
                {resource_filter}
                GROUP BY sync_status
                """,
                parameters,
            ).fetchall()
            event_rows = connection.execute(
                f"""
                SELECT status, COUNT(*) AS count
                FROM rag_index_outbox
                {event_filter}
                GROUP BY status
                """,
                parameters,
            ).fetchall()
            pending_filter = (
                "WHERE user_id = ? AND status IN ('pending', 'failed')"
                if user_id
                else "WHERE status IN ('pending', 'failed')"
            )
            oldest_row = connection.execute(
                f"""
                SELECT MIN(created_at) AS oldest_pending_at
                FROM rag_index_outbox
                {pending_filter}
                """,
                parameters,
            ).fetchone()
            synced_filter = (
                "WHERE user_id = ? AND last_synced_at IS NOT NULL"
                if user_id
                else "WHERE last_synced_at IS NOT NULL"
            )
            synced_row = connection.execute(
                f"""
                SELECT MAX(last_synced_at) AS last_synced_at
                FROM rag_resource_status
                {synced_filter}
                """,
                parameters,
            ).fetchone()
            failure_filter = (
                "WHERE user_id = ? AND status = 'failed'"
                if user_id
                else "WHERE status = 'failed'"
            )
            failure_rows = connection.execute(
                f"""
                SELECT *
                FROM rag_index_outbox
                {failure_filter}
                ORDER BY available_at DESC, created_at DESC
                LIMIT ?
                """,
                (*parameters, bounded_limit),
            ).fetchall()
        resources = {str(row["sync_status"]): int(row["count"]) for row in resource_rows}
        events = {str(row["status"]): int(row["count"]) for row in event_rows}
        return RAGSyncOverview(
            resource_count=sum(resources.values()),
            ready_count=resources.get("ready", 0),
            pending_resource_count=(
                resources.get("pending", 0) + resources.get("processing", 0)
            ),
            failed_resource_count=resources.get("failed", 0),
            deleted_count=resources.get("deleted", 0),
            pending_event_count=events.get("pending", 0),
            processing_event_count=events.get("processing", 0),
            failed_event_count=events.get("failed", 0),
            oldest_pending_at=(
                datetime.fromisoformat(oldest_row["oldest_pending_at"])
                if oldest_row is not None
                and oldest_row["oldest_pending_at"] is not None
                else None
            ),
            last_synced_at=(
                datetime.fromisoformat(synced_row["last_synced_at"])
                if synced_row is not None and synced_row["last_synced_at"] is not None
                else None
            ),
            recent_failures=[_event_from_row(row) for row in failure_rows],
        )

    def list_statuses(
        self,
        *,
        user_id: str | None = None,
    ) -> list[RAGResourceStatus]:
        """按方法参数限定的主键或用户范围列出statuses。"""
        where_clause = "WHERE user_id = ?" if user_id else ""
        parameters: tuple[object, ...] = (user_id,) if user_id else ()
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                f"""
                SELECT *
                FROM rag_resource_status
                {where_clause}
                ORDER BY user_id, resource_type, resource_id
                """,
                parameters,
            ).fetchall()
        return [_status_from_row(row) for row in rows]

    def retry_failed(
        self,
        *,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        """按方法参数限定的主键或用户范围重试failed。"""
        bounded_limit = max(1, min(1_000, int(limit)))
        now = _utc_now().isoformat()
        user_filter = "AND outbox.user_id = ?" if user_id else ""
        parameters: tuple[object, ...] = (user_id,) if user_id else ()
        with get_connection() as connection:
            init_database(connection)
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                f"""
                SELECT outbox.event_id
                FROM rag_index_outbox AS outbox
                JOIN rag_resource_status AS resource
                  ON resource.last_event_id = outbox.event_id
                WHERE outbox.status = 'failed'
                {user_filter}
                ORDER BY outbox.created_at
                LIMIT ?
                """,
                (*parameters, bounded_limit),
            ).fetchall()
            event_ids = [str(row["event_id"]) for row in rows]
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                connection.execute(
                    f"""
                    UPDATE rag_index_outbox
                    SET status = 'pending', attempt_count = 0, available_at = ?,
                        last_error_code = NULL, last_error_message = NULL,
                        completed_at = NULL
                    WHERE event_id IN ({placeholders})
                    """,
                    [now, *event_ids],
                )
                connection.execute(
                    f"""
                    UPDATE rag_resource_status
                    SET sync_status = 'pending', last_error_code = NULL,
                        updated_at = ?
                    WHERE last_event_id IN ({placeholders})
                    """,
                    [now, *event_ids],
                )
            connection.commit()
        return len(event_ids)


def _event_from_row(row: sqlite3.Row) -> RAGIndexEvent:
    return RAGIndexEvent(
        event_id=row["event_id"],
        user_id=row["user_id"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        resource_version=row["resource_version"],
        operation=row["operation"],
        status=row["status"],
        attempt_count=row["attempt_count"],
        available_at=datetime.fromisoformat(row["available_at"]),
        last_error_code=row["last_error_code"],
        last_error_message=row["last_error_message"],
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=(
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
    )


def _status_from_row(row: sqlite3.Row) -> RAGResourceStatus:
    return RAGResourceStatus(
        user_id=row["user_id"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        desired_version=row["desired_version"],
        indexed_version=row["indexed_version"],
        indexed_document_id=row["indexed_document_id"],
        sync_status=row["sync_status"],
        last_event_id=row["last_event_id"],
        last_synced_at=(
            datetime.fromisoformat(row["last_synced_at"])
            if row["last_synced_at"] is not None
            else None
        ),
        last_error_code=row["last_error_code"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


rag_sync_repository = RAGSyncRepository()
