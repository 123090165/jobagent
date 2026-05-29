from __future__ import annotations

from pathlib import Path

from app.schemas.report import FinalReport
from app.storage.database import get_connection
from app.storage.repositories import (
    get_analysis_record,
    get_job_posting,
    list_analysis_records,
    list_job_postings,
    save_analysis_record,
)


def save_final_report(report: FinalReport, *, database_path: str | Path | None = None) -> int:
    connection = get_connection(database_path)
    try:
        return save_analysis_record(connection, report)
    finally:
        connection.close()


def load_analysis_record(record_id: int, *, database_path: str | Path | None = None) -> dict | None:
    connection = get_connection(database_path)
    try:
        return get_analysis_record(connection, record_id)
    finally:
        connection.close()


def list_saved_analysis_records(
    *,
    limit: int = 20,
    keyword: str | None = None,
    database_path: str | Path | None = None,
) -> list[dict]:
    connection = get_connection(database_path)
    try:
        return list_analysis_records(connection, limit=limit, keyword=keyword)
    finally:
        connection.close()


def list_saved_job_postings(
    *,
    limit: int = 20,
    keyword: str | None = None,
    database_path: str | Path | None = None,
) -> list[dict]:
    connection = get_connection(database_path)
    try:
        return list_job_postings(connection, limit=limit, keyword=keyword)
    finally:
        connection.close()


def load_job_posting(job_id: int, *, database_path: str | Path | None = None) -> dict | None:
    connection = get_connection(database_path)
    try:
        return get_job_posting(connection, job_id)
    finally:
        connection.close()
