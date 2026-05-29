from __future__ import annotations

from pathlib import Path

from app.schemas.application import ApplicationStatus
from app.storage.database import get_connection
from app.storage.repositories import (
    get_application_record,
    list_application_records,
    update_application_record,
    upsert_application_record,
)


def save_application(
    *,
    job_id: int,
    status: ApplicationStatus = "interested",
    notes: str | None = None,
    next_action: str | None = None,
    resume_version_label: str | None = None,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        return upsert_application_record(
            connection,
            job_id=job_id,
            status=status,
            notes=notes,
            next_action=next_action,
            resume_version_label=resume_version_label,
        )
    finally:
        connection.close()


def update_application(
    *,
    application_id: int,
    status: ApplicationStatus | None = None,
    notes: str | None = None,
    next_action: str | None = None,
    resume_version_label: str | None = None,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        return update_application_record(
            connection,
            application_id=application_id,
            status=status,
            notes=notes,
            next_action=next_action,
            resume_version_label=resume_version_label,
        )
    finally:
        connection.close()


def list_applications(
    *,
    limit: int = 20,
    status: str | None = None,
    keyword: str | None = None,
    database_path: str | Path | None = None,
) -> list[dict]:
    connection = get_connection(database_path)
    try:
        return list_application_records(
            connection,
            limit=limit,
            status=status,
            keyword=keyword,
        )
    finally:
        connection.close()


def load_application(
    application_id: int,
    *,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        return get_application_record(connection, application_id)
    finally:
        connection.close()
