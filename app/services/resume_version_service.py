from __future__ import annotations

from pathlib import Path

from app.storage.database import get_connection
from app.storage.repositories import (
    create_resume_version,
    get_resume_version,
    list_resume_versions,
)


def save_resume_version(
    *,
    label: str,
    base_resume_text: str,
    tailored_resume_text: str | None = None,
    target_job_id: int | None = None,
    source_analysis_record_id: int | None = None,
    notes: str | None = None,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        return create_resume_version(
            connection,
            label=label,
            base_resume_text=base_resume_text,
            tailored_resume_text=tailored_resume_text,
            target_job_id=target_job_id,
            source_analysis_record_id=source_analysis_record_id,
            notes=notes,
        )
    finally:
        connection.close()


def list_saved_resume_versions(
    *,
    limit: int = 20,
    keyword: str | None = None,
    target_job_id: int | None = None,
    database_path: str | Path | None = None,
) -> list[dict]:
    connection = get_connection(database_path)
    try:
        return list_resume_versions(
            connection,
            limit=limit,
            keyword=keyword,
            target_job_id=target_job_id,
        )
    finally:
        connection.close()


def load_resume_version(
    resume_version_id: int,
    *,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        return get_resume_version(connection, resume_version_id)
    finally:
        connection.close()
