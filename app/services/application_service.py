from __future__ import annotations

from pathlib import Path

from app.schemas.application import ApplicationStatus
from app.services.errors import JobAgentError
from app.services.storage_service import save_final_report
from app.storage.database import get_connection
from app.storage.repositories import (
    get_application_record,
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
        return upsert_application_record(
            connection,
            job_id=job_id,
            status=status,
            notes=notes,
            next_action=next_action,
            resume_version_id=resume_version_id,
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
    resume_version_id: int | None = None,
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
            resume_version_id=resume_version_id,
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
        return {
            "application": application,
            "application_id": application["id"],
            "record_id": record_id,
            "workflow_steps": workflow_steps,
            **workflow_result.final_report.model_dump(),
        }
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
