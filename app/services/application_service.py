from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas.application import ApplicationAnalysisSummary, ApplicationStatus
from app.services.errors import JobAgentError
from app.services.storage_service import save_final_report
from app.storage.database import get_connection
from app.storage.repositories import (
    get_application_record,
    list_analysis_records_for_application,
    list_application_records,
    get_resume_version,
    update_application_record,
    upsert_application_record,
)
from app.workflows.job_analysis_workflow import run_job_analysis_workflow


def save_application(
    *,
    job_id: int,
    status: ApplicationStatus = "interested",
    notes: str | None = None,
    next_action: str | None = None,
    resume_version_id: int | None = None,
    resume_version_label: str | None = None,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        record = upsert_application_record(
            connection,
            job_id=job_id,
            status=status,
            notes=notes,
            next_action=next_action,
            resume_version_id=resume_version_id,
            resume_version_label=resume_version_label,
        )
        return _attach_analysis_summary(connection, record)
    finally:
        connection.close()


def update_application(
    *,
    application_id: int,
    status: ApplicationStatus | None = None,
    notes: str | None = None,
    next_action: str | None = None,
    resume_version_id: int | None = None,
    resume_version_label: str | None = None,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        record = update_application_record(
            connection,
            application_id=application_id,
            status=status,
            notes=notes,
            next_action=next_action,
            resume_version_id=resume_version_id,
            resume_version_label=resume_version_label,
        )
        return _attach_analysis_summary(connection, record)
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
        records = list_application_records(
            connection,
            limit=limit,
            status=status,
            keyword=keyword,
        )
        return [_attach_analysis_summary(connection, record) for record in records]
    finally:
        connection.close()


def load_application(
    application_id: int,
    *,
    database_path: str | Path | None = None,
) -> dict | None:
    connection = get_connection(database_path)
    try:
        record = get_application_record(connection, application_id)
        return _attach_analysis_summary(connection, record)
    finally:
        connection.close()


def analyze_application(
    application_id: int,
    *,
    resume_text: str | None = None,
    resume_version_id: int | None = None,
    mode: str = "mock",
    database_path: str | Path | None = None,
) -> dict:
    if mode != "mock":
        raise JobAgentError(
            f"unsupported analysis mode: {mode}",
            error_code="application_analysis_mode_unsupported",
            status_code=400,
        )

    connection = get_connection(database_path)
    try:
        application = get_application_record(connection, application_id)
        if application is None:
            raise JobAgentError(
                "application not found",
                error_code="application_not_found",
                status_code=404,
            )

        jd_text = _build_application_job_context(application)
        if not jd_text:
            raise JobAgentError(
                "application job description is missing",
                error_code="application_job_description_missing",
                status_code=400,
            )

        normalized_resume_text = _resolve_resume_text(
            connection,
            resume_text=resume_text,
            resume_version_id=resume_version_id,
        )

        workflow_result = run_job_analysis_workflow(
            resume_text=normalized_resume_text,
            jd_text=jd_text,
        )
        workflow_steps = [step.model_dump() for step in workflow_result.state.steps]
        record_id = save_final_report(
            workflow_result.final_report,
            application_id=application_id,
            workflow_steps=workflow_steps,
            database_path=database_path,
        )
        application_with_summary = _attach_analysis_summary(connection, application)
        return {
            "application": application_with_summary,
            "application_id": application["id"],
            "record_id": record_id,
            "workflow_steps": workflow_steps,
            **workflow_result.final_report.model_dump(),
        }
    finally:
        connection.close()


def build_application_analysis_summary(
    application_id: int,
    *,
    database_path: str | Path | None = None,
) -> ApplicationAnalysisSummary:
    connection = get_connection(database_path)
    try:
        return _build_application_analysis_summary(connection, application_id)
    finally:
        connection.close()


def _build_application_job_context(application: dict) -> str:
    raw_jd = (application.get("raw_jd") or "").strip()
    if not raw_jd:
        return ""
    notes = (application.get("notes") or "").strip()
    if not notes:
        return raw_jd
    return f"{raw_jd}\n\nApplication notes:\n{notes}"


def _attach_analysis_summary(connection, record: dict | None) -> dict | None:
    if record is None:
        return None
    enriched = dict(record)
    enriched["analysis_summary"] = _build_application_analysis_summary(
        connection,
        int(record["id"]),
    ).model_dump()
    return enriched


def _build_application_analysis_summary(
    connection,
    application_id: int,
) -> ApplicationAnalysisSummary:
    records = list_analysis_records_for_application(connection, application_id)
    if not records:
        return ApplicationAnalysisSummary()

    latest = records[0]
    return ApplicationAnalysisSummary(
        analysis_count=len(records),
        latest_analysis_record_id=int(latest["id"]),
        last_analyzed_at=latest.get("created_at"),
        last_match_score=_extract_match_score(latest),
        last_analysis_quality=_extract_analysis_quality(latest),
        latest_report_title=latest.get("job_title") or "Application Analysis",
        has_analysis=True,
    )


def _extract_match_score(record: dict[str, Any]) -> float | None:
    for value in (
        record.get("overall_score"),
        _get_nested(record, "match_report", "score"),
        _get_nested(record, "match_report", "overall_score"),
        _get_nested(record, "workflow_result", "match_report", "score"),
        _get_nested(record, "workflow_result", "match_report", "overall_score"),
    ):
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _extract_analysis_quality(record: dict[str, Any]) -> str | None:
    value = _get_nested(record, "report", "analysis_quality", "overall_quality_label")
    if isinstance(value, str):
        return value
    value = _get_nested(record, "analysis_quality", "overall_quality_label")
    if isinstance(value, str):
        return value
    return None


def _get_nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _resolve_resume_text(
    connection,
    *,
    resume_text: str | None,
    resume_version_id: int | None,
) -> str:
    normalized_resume_text = (resume_text or "").strip()
    if normalized_resume_text:
        return normalized_resume_text
    if resume_version_id is None:
        raise JobAgentError(
            "resume_text cannot be empty",
            error_code="analysis_input_invalid",
            status_code=400,
        )
    resume_version = get_resume_version(connection, resume_version_id)
    if resume_version is None:
        raise JobAgentError(
            "resume version not found",
            error_code="resume_version_not_found",
            status_code=404,
        )
    stored_resume_text = (
        resume_version.get("tailored_resume_text")
        or resume_version.get("base_resume_text")
        or ""
    ).strip()
    if not stored_resume_text:
        raise JobAgentError(
            "resume_text cannot be empty",
            error_code="analysis_input_invalid",
            status_code=400,
        )
    return stored_resume_text
