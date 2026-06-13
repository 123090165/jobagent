from __future__ import annotations

import json
from pathlib import Path
from sqlite3 import Row

from app.schemas.confirmed_profile import (
    ConfirmedProfileCreateRequest,
    ConfirmedProfileCreateResponse,
    ConfirmedProfileRecordDetail,
    ConfirmedProfileRecordSummary,
    MissingInfoAnswerInput,
    ProfileSuggestionDecisionInput,
)
from app.schemas.profile_review import (
    ConfirmedResumeProfileResult,
    ResumeProfileConfirmationSummary,
    ResumeProfileUserEdits,
)
from app.schemas.resume import ResumeProfile
from app.services.errors import JobAgentError
from app.storage.database import get_connection, init_database


def create_confirmed_profile_record(
    request: ConfirmedProfileCreateRequest,
    database_path: str | Path | None = None,
) -> ConfirmedProfileCreateResponse:
    normalized_resume = request.raw_resume_text.strip()
    if not normalized_resume:
        raise JobAgentError(
            "raw_resume_text is required",
            error_code="raw_resume_text_required",
        )

    missing_info_answers = _normalize_missing_info_answers(
        request.missing_info_answers
    )
    suggestion_decisions = list(request.suggestion_decisions)
    target_roles = request.confirmed_result.user_confirmed_data.target_roles

    with get_connection(database_path) as connection:
        init_database(connection)
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO confirmed_profile_records (
                    resume_record_id,
                    raw_resume_text,
                    baseline_profile_json,
                    confirmed_profile_json,
                    user_edits_json,
                    confirmation_summary_json,
                    remaining_warnings_json,
                    suggestion_decisions_json,
                    missing_info_answers_json,
                    confidence_label,
                    target_roles_json,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.resume_record_id,
                    normalized_resume,
                    request.baseline_profile.model_dump_json(),
                    request.confirmed_result.confirmed_profile.model_dump_json(),
                    request.confirmed_result.user_confirmed_data.model_dump_json(),
                    request.confirmed_result.confirmation_summary.model_dump_json(),
                    json.dumps(
                        request.confirmed_result.remaining_warnings,
                        ensure_ascii=False,
                    ),
                    _dump_model_list(suggestion_decisions),
                    _dump_model_list(missing_info_answers),
                    request.confirmed_result.confidence_label,
                    json.dumps(target_roles, ensure_ascii=False),
                    request.notes,
                ),
            )
            record_id = int(cursor.lastrowid)

        detail = get_confirmed_profile_record(record_id, database_path=database_path)
        return ConfirmedProfileCreateResponse(
            id=record_id,
            summary=_detail_to_summary(detail),
        )


def list_confirmed_profile_records(
    limit: int = 20,
    database_path: str | Path | None = None,
) -> list[ConfirmedProfileRecordSummary]:
    safe_limit = max(1, min(int(limit), 100))
    with get_connection(database_path) as connection:
        init_database(connection)
        rows = connection.execute(
            """
            SELECT *
            FROM confirmed_profile_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def get_confirmed_profile_record(
    record_id: int,
    database_path: str | Path | None = None,
) -> ConfirmedProfileRecordDetail:
    with get_connection(database_path) as connection:
        init_database(connection)
        row = connection.execute(
            """
            SELECT *
            FROM confirmed_profile_records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

    if row is None:
        raise JobAgentError(
            "confirmed profile not found",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )
    return _row_to_detail(row)


def _row_to_detail(row: Row) -> ConfirmedProfileRecordDetail:
    confirmed_profile = ResumeProfile.model_validate_json(row["confirmed_profile_json"])
    user_edits = ResumeProfileUserEdits.model_validate_json(row["user_edits_json"])
    confirmation_summary = ResumeProfileConfirmationSummary.model_validate_json(
        row["confirmation_summary_json"]
    )
    remaining_warnings = json.loads(row["remaining_warnings_json"])
    confirmed_result = ConfirmedResumeProfileResult(
        confirmed_profile=confirmed_profile,
        user_confirmed_data=user_edits,
        confirmation_summary=confirmation_summary,
        remaining_warnings=remaining_warnings,
        confidence_label=row["confidence_label"],
    )
    return ConfirmedProfileRecordDetail(
        id=int(row["id"]),
        raw_resume_text=row["raw_resume_text"],
        baseline_profile=ResumeProfile.model_validate_json(row["baseline_profile_json"]),
        confirmed_result=confirmed_result,
        suggestion_decisions=[
            ProfileSuggestionDecisionInput.model_validate(item)
            for item in json.loads(row["suggestion_decisions_json"])
        ],
        missing_info_answers=[
            MissingInfoAnswerInput.model_validate(item)
            for item in json.loads(row["missing_info_answers_json"])
        ],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_summary(row: Row) -> ConfirmedProfileRecordSummary:
    detail = _row_to_detail(row)
    return _detail_to_summary(detail)


def _detail_to_summary(
    detail: ConfirmedProfileRecordDetail,
) -> ConfirmedProfileRecordSummary:
    profile = detail.confirmed_result.confirmed_profile
    return ConfirmedProfileRecordSummary(
        id=detail.id,
        confidence_label=detail.confirmed_result.confidence_label,
        target_roles=detail.confirmed_result.user_confirmed_data.target_roles,
        skill_count=len(profile.skills),
        project_count=len(profile.projects),
        work_experience_count=len(profile.work_experiences),
        decision_count=len(detail.suggestion_decisions),
        missing_answer_count=len(detail.missing_info_answers),
        created_at=detail.created_at,
        updated_at=detail.updated_at,
    )


def _normalize_missing_info_answers(
    answers: list[MissingInfoAnswerInput],
) -> list[MissingInfoAnswerInput]:
    return [
        MissingInfoAnswerInput(
            question=answer.question.strip(),
            answer=answer.answer.strip(),
        )
        for answer in answers
        if answer.question.strip() and answer.answer.strip()
    ]


def _dump_model_list(
    items: list[ProfileSuggestionDecisionInput] | list[MissingInfoAnswerInput],
) -> str:
    return json.dumps(
        [item.model_dump(mode="json") for item in items],
        ensure_ascii=False,
    )
