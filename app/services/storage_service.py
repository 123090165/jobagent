from __future__ import annotations

from pathlib import Path

from app.schemas.report import FinalReport
from app.storage.database import get_connection
from app.storage.repositories import get_analysis_record, save_analysis_record


def save_final_report(report: FinalReport, *, database_path: str | Path | None = None) -> int:
    with get_connection(database_path) as connection:
        return save_analysis_record(connection, report)


def load_analysis_record(record_id: int, *, database_path: str | Path | None = None) -> dict | None:
    with get_connection(database_path) as connection:
        return get_analysis_record(connection, record_id)
