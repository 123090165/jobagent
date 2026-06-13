from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from app.schemas.confirmed_profile import (
    ConfirmedProfileCreateRequest,
    MissingInfoAnswerInput,
    ProfileSuggestionDecisionInput,
)
from app.schemas.profile_review import (
    ConfirmedResumeProfileResult,
    ResumeProfileConfirmationSummary,
    ResumeProfileUserEdits,
)
from app.schemas.resume import ResumeProfile
from app.services.confirmed_profile_storage_service import (
    create_confirmed_profile_record,
    get_confirmed_profile_record,
    list_confirmed_profile_records,
)
from app.services.errors import JobAgentError
from app.storage.database import init_database


def _request() -> ConfirmedProfileCreateRequest:
    profile = ResumeProfile(
        raw_text="Skills: Python\nProjects: JobAgent built FastAPI APIs.",
        skills=["Python", "FastAPI"],
        projects=[
            {
                "name": "JobAgent",
                "description": "Built FastAPI APIs.",
                "technologies": ["FastAPI"],
                "highlights": [],
                "raw_text": "JobAgent built FastAPI APIs.",
            }
        ],
    )
    user_edits = ResumeProfileUserEdits(
        target_roles=["Backend Engineer"],
        additional_skills=["Python", "FastAPI"],
        project_clarifications=["JobAgent | Built FastAPI APIs."],
        notes="Prefers backend roles.",
    )
    confirmed_result = ConfirmedResumeProfileResult(
        confirmed_profile=profile,
        user_confirmed_data=user_edits,
        confirmation_summary=ResumeProfileConfirmationSummary(
            confirmed_sections=["target_roles", "skills", "projects", "notes"],
            added_target_roles=["Backend Engineer"],
            added_skills=["Python", "FastAPI"],
            added_project_clarifications_count=1,
        ),
        remaining_warnings=[],
        confidence_label="medium",
    )
    return ConfirmedProfileCreateRequest(
        raw_resume_text=profile.raw_text,
        baseline_profile=profile,
        confirmed_result=confirmed_result,
        suggestion_decisions=[
            ProfileSuggestionDecisionInput(
                section="project",
                item_index=0,
                field="description",
                suggested_value="Built FastAPI APIs.",
                source_quote="Built FastAPI APIs.",
                decision_status="accepted",
            )
        ],
        missing_info_answers=[
            MissingInfoAnswerInput(
                question="What target roles should this profile prioritize?",
                answer="Backend Engineer",
            )
        ],
        notes="Saved from profile review.",
    )


def test_create_confirmed_profile_record_saves_record(tmp_path) -> None:
    database_path = tmp_path / "jobagent_test.sqlite3"

    response = create_confirmed_profile_record(_request(), database_path=database_path)

    assert response.id > 0
    assert response.summary.skill_count == 2
    assert response.summary.project_count == 1


def test_list_confirmed_profile_records_returns_summary(tmp_path) -> None:
    database_path = tmp_path / "jobagent_test.sqlite3"
    create_confirmed_profile_record(_request(), database_path=database_path)

    records = list_confirmed_profile_records(database_path=database_path)

    assert len(records) == 1
    assert records[0].target_roles == ["Backend Engineer"]
    assert records[0].decision_count == 1
    assert records[0].missing_answer_count == 1


def test_get_confirmed_profile_record_returns_detail(tmp_path) -> None:
    database_path = tmp_path / "jobagent_test.sqlite3"
    created = create_confirmed_profile_record(_request(), database_path=database_path)

    detail = get_confirmed_profile_record(created.id, database_path=database_path)

    assert detail.id == created.id
    assert detail.confirmed_result.confirmed_profile.skills == ["Python", "FastAPI"]
    assert detail.notes == "Saved from profile review."


def test_suggestion_decisions_json_is_persisted(tmp_path) -> None:
    database_path = tmp_path / "jobagent_test.sqlite3"
    created = create_confirmed_profile_record(_request(), database_path=database_path)

    detail = get_confirmed_profile_record(created.id, database_path=database_path)

    assert detail.suggestion_decisions[0].decision_status == "accepted"
    assert detail.suggestion_decisions[0].source_quote == "Built FastAPI APIs."


def test_missing_info_answers_json_is_persisted(tmp_path) -> None:
    database_path = tmp_path / "jobagent_test.sqlite3"
    created = create_confirmed_profile_record(_request(), database_path=database_path)

    detail = get_confirmed_profile_record(created.id, database_path=database_path)

    assert detail.missing_info_answers[0].answer == "Backend Engineer"


def test_invalid_decision_status_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ProfileSuggestionDecisionInput(
            section="project",
            field="description",
            suggested_value="x",
            decision_status="maybe",
        )


def test_not_found_id_raises_jobagent_error(tmp_path) -> None:
    database_path = tmp_path / "jobagent_test.sqlite3"

    with pytest.raises(JobAgentError) as exc_info:
        get_confirmed_profile_record(999, database_path=database_path)

    assert exc_info.value.error_code == "confirmed_profile_not_found"


def test_database_initialization_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "jobagent_test.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row

    init_database(connection)
    init_database(connection)

    table = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'confirmed_profile_records'
        """
    ).fetchone()
    assert table is not None
