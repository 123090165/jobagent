from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

from app.schemas.job_application import (
    ApplicationEvent,
    ApplicationEventSource,
    ApplicationEventType,
    ApplicationNextAction,
    ApplicationStage,
    JobApplication,
)
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def _connection_scope(
    connection: sqlite3.Connection | None,
) -> Iterator[tuple[sqlite3.Connection, bool]]:
    # 外部连接用于跨资源事务；仓储只提交自己创建的连接。
    if connection is not None:
        yield connection, False
        return
    owned = get_connection()
    try:
        init_database(owned)
        yield owned, True
    finally:
        owned.close()


class JobApplicationRepository:
    def create_for_job(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        stage: ApplicationStage = "not_started",
        next_action: ApplicationNextAction = "generate_greeting",
        source: ApplicationEventSource = "user",
        detail: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> JobApplication:
        with _connection_scope(connection) as (database, owns_connection):
            existing = self._get_by_saved_job(
                database,
                user_id=user_id,
                saved_job_id=saved_job_id,
            )
            if existing is not None:
                return existing
            now = _utc_now()
            item = JobApplication(
                application_id=str(uuid4()),
                user_id=user_id,
                saved_job_id=saved_job_id,
                stage=stage,
                next_action=next_action,
                last_activity_at=now,
                contacted_at=now if stage == "contacted" else None,
                created_at=now,
                updated_at=now,
            )
            database.execute(
                """
                INSERT INTO job_applications (
                    application_id, user_id, saved_job_id, stage, next_action,
                    last_activity_at, contacted_at, replied_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._application_values(item),
            )
            self._insert_event(
                database,
                application_id=item.application_id,
                user_id=user_id,
                event_type="stage_changed",
                source=source,
                detail=detail or (
                    "Application tracking started."
                    if stage == "not_started"
                    else "External application progress recorded."
                ),
                metadata={"from_stage": None, "to_stage": stage},
                created_at=now,
            )
            if owns_connection:
                database.commit()
            return item

    def get(
        self,
        *,
        user_id: str,
        application_id: str,
        connection: sqlite3.Connection | None = None,
    ) -> JobApplication | None:
        with _connection_scope(connection) as (database, _):
            row = database.execute(
                "SELECT * FROM job_applications WHERE user_id = ? AND application_id = ?",
                (user_id, application_id),
            ).fetchone()
        return self._row_to_application(row) if row is not None else None

    def get_by_saved_job(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        connection: sqlite3.Connection | None = None,
    ) -> JobApplication | None:
        with _connection_scope(connection) as (database, _):
            return self._get_by_saved_job(
                database,
                user_id=user_id,
                saved_job_id=saved_job_id,
            )

    def update_tracking(
        self,
        *,
        user_id: str,
        application_id: str,
        stage: ApplicationStage,
        next_action: ApplicationNextAction,
        detail: str | None,
        source: ApplicationEventSource = "user",
        connection: sqlite3.Connection | None = None,
    ) -> JobApplication | None:
        with _connection_scope(connection) as (database, owns_connection):
            existing = self.get(
                user_id=user_id,
                application_id=application_id,
                connection=database,
            )
            if existing is None:
                return None
            now = _utc_now()
            contacted_at = existing.contacted_at
            replied_at = existing.replied_at
            if stage == "contacted" and contacted_at is None:
                contacted_at = now
            if stage == "recruiter_replied" and replied_at is None:
                replied_at = now
            updated = existing.model_copy(
                update={
                    "stage": stage,
                    "next_action": next_action,
                    "last_activity_at": now,
                    "contacted_at": contacted_at,
                    "replied_at": replied_at,
                    "updated_at": now,
                }
            )
            database.execute(
                """
                UPDATE job_applications
                SET stage = ?, next_action = ?, last_activity_at = ?,
                    contacted_at = ?, replied_at = ?, updated_at = ?
                WHERE user_id = ? AND application_id = ?
                """,
                (
                    updated.stage,
                    updated.next_action,
                    updated.last_activity_at.isoformat(),
                    updated.contacted_at.isoformat() if updated.contacted_at else None,
                    updated.replied_at.isoformat() if updated.replied_at else None,
                    updated.updated_at.isoformat(),
                    user_id,
                    application_id,
                ),
            )
            if stage != existing.stage:
                self._insert_event(
                    database,
                    application_id=application_id,
                    user_id=user_id,
                    event_type="stage_changed",
                    source=source,
                    detail=detail or "Application stage updated.",
                    metadata={"from_stage": existing.stage, "to_stage": stage},
                    created_at=now,
                )
            if owns_connection:
                database.commit()
            return updated

    def add_event(
        self,
        *,
        application_id: str,
        user_id: str,
        event_type: ApplicationEventType,
        source: ApplicationEventSource,
        detail: str | None = None,
        metadata: dict[str, object] | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> ApplicationEvent:
        with _connection_scope(connection) as (database, owns_connection):
            event = self._insert_event(
                database,
                application_id=application_id,
                user_id=user_id,
                event_type=event_type,
                source=source,
                detail=detail,
                metadata=metadata or {},
                created_at=_utc_now(),
            )
            if owns_connection:
                database.commit()
            return event

    def list_events(
        self,
        *,
        user_id: str,
        application_id: str,
        limit: int = 100,
    ) -> list[ApplicationEvent]:
        bounded_limit = max(1, min(limit, 200))
        with _connection_scope(None) as (database, _):
            rows = database.execute(
                """
                SELECT * FROM application_events
                WHERE user_id = ? AND application_id = ?
                ORDER BY created_at DESC, event_id DESC
                LIMIT ?
                """,
                (user_id, application_id, bounded_limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _get_by_saved_job(
        connection: sqlite3.Connection,
        *,
        user_id: str,
        saved_job_id: str,
    ) -> JobApplication | None:
        row = connection.execute(
            "SELECT * FROM job_applications WHERE user_id = ? AND saved_job_id = ?",
            (user_id, saved_job_id),
        ).fetchone()
        return JobApplicationRepository._row_to_application(row) if row is not None else None

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        *,
        application_id: str,
        user_id: str,
        event_type: ApplicationEventType,
        source: ApplicationEventSource,
        detail: str | None,
        metadata: dict[str, object],
        created_at: datetime,
    ) -> ApplicationEvent:
        event = ApplicationEvent(
            event_id=str(uuid4()),
            application_id=application_id,
            user_id=user_id,
            event_type=event_type,
            source=source,
            detail=detail,
            metadata=metadata,
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO application_events (
                event_id, application_id, user_id, event_type, source,
                detail, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.application_id,
                event.user_id,
                event.event_type,
                event.source,
                event.detail,
                json.dumps(event.metadata),
                event.created_at.isoformat(),
            ),
        )
        return event

    @staticmethod
    def _application_values(item: JobApplication) -> tuple[object, ...]:
        return (
            item.application_id,
            item.user_id,
            item.saved_job_id,
            item.stage,
            item.next_action,
            item.last_activity_at.isoformat(),
            item.contacted_at.isoformat() if item.contacted_at else None,
            item.replied_at.isoformat() if item.replied_at else None,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
        )

    @staticmethod
    def _row_to_application(row: object) -> JobApplication:
        return JobApplication(
            application_id=row["application_id"],
            user_id=row["user_id"],
            saved_job_id=row["saved_job_id"],
            stage=row["stage"],
            next_action=row["next_action"],
            last_activity_at=datetime.fromisoformat(row["last_activity_at"]),
            contacted_at=(
                datetime.fromisoformat(row["contacted_at"])
                if row["contacted_at"]
                else None
            ),
            replied_at=(
                datetime.fromisoformat(row["replied_at"])
                if row["replied_at"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_event(row: object) -> ApplicationEvent:
        return ApplicationEvent(
            event_id=row["event_id"],
            application_id=row["application_id"],
            user_id=row["user_id"],
            event_type=row["event_type"],
            source=row["source"],
            detail=row["detail"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


job_application_repository = JobApplicationRepository()
