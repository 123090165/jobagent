from __future__ import annotations

from frontend.profile_review_state import (
    apply_suggestion_to_profile_draft,
    build_confirmed_profile_save_payload,
    build_confirm_user_edits_from_profile_draft,
    dedupe_skills,
)


def _draft() -> dict:
    return {
        "skills": ["Python"],
        "projects": [
            {
                "name": "JobAgent",
                "description": "Built profile review flow.",
                "technologies": ["FastAPI"],
                "highlights": [],
                "raw_text": "JobAgent - built FastAPI APIs.",
            }
        ],
        "work_experiences": [],
        "education": [],
        "certificates": [],
        "highlights": [],
        "target_roles": ["Backend Engineer"],
        "preferred_locations": [],
        "constraints": [],
        "notes": "",
    }


def test_dedupe_skills_is_case_insensitive() -> None:
    assert dedupe_skills(["Python", "python", " FastAPI "]) == ["Python", "FastAPI"]


def test_accept_skill_suggestion_adds_skill() -> None:
    draft = apply_suggestion_to_profile_draft(
        _draft(),
        {
            "section": "skills",
            "field": "skills",
            "suggested_value": ["Python", "LangGraph"],
        },
    )

    assert draft["skills"] == ["Python", "LangGraph"]


def test_reject_suggestion_does_not_change_draft() -> None:
    draft = _draft()
    unchanged = draft.copy()

    assert draft == unchanged


def test_edit_suggestion_uses_edited_value() -> None:
    draft = apply_suggestion_to_profile_draft(
        _draft(),
        {
            "section": "skills",
            "field": "skills",
            "suggested_value": "LangGraph",
        },
        edited_value="Pydantic",
    )

    assert "Pydantic" in draft["skills"]
    assert "LangGraph" not in draft["skills"]


def test_project_suggestion_applies_to_correct_item_index() -> None:
    draft = apply_suggestion_to_profile_draft(
        _draft(),
        {
            "section": "project",
            "item_index": 0,
            "field": "highlights",
            "suggested_value": "passed 300 tests",
        },
    )

    assert draft["projects"][0]["highlights"] == ["passed 300 tests"]


def test_unknown_section_does_not_crash() -> None:
    draft = apply_suggestion_to_profile_draft(
        _draft(),
        {
            "section": "unknown",
            "field": "summary",
            "suggested_value": "ignored",
        },
    )

    assert draft["skills"] == ["Python"]
    assert draft["_warnings"]


def test_build_confirm_user_edits_from_profile_draft() -> None:
    user_edits = build_confirm_user_edits_from_profile_draft(_draft())

    assert user_edits.target_roles == ["Backend Engineer"]
    assert user_edits.additional_skills == ["Python"]
    assert user_edits.project_clarifications


def _baseline_review() -> dict:
    return {
        "parsed_profile": {
            "raw_text": "Skills: Python",
            "skills": ["Python"],
            "projects": [],
            "work_experiences": [],
            "education": [],
            "certificates": [],
            "highlights": [],
            "missing_info": [],
        }
    }


def _confirmed_profile_result() -> dict:
    return {
        "confirmed_profile": _baseline_review()["parsed_profile"],
        "user_confirmed_data": {
            "target_roles": ["Backend Engineer"],
            "preferred_locations": [],
            "additional_skills": ["Python"],
            "project_clarifications": [],
            "work_experience_clarifications": [],
            "constraints": [],
            "notes": "Saved note",
        },
        "confirmation_summary": {
            "confirmed_sections": ["target_roles", "skills", "notes"],
            "added_target_roles": ["Backend Engineer"],
            "added_skills": ["Python"],
            "added_project_clarifications_count": 0,
            "added_work_experience_clarifications_count": 0,
            "constraints_count": 0,
        },
        "remaining_warnings": [],
        "confidence_label": "medium",
    }


def _suggestion() -> dict:
    return {
        "section": "project",
        "item_index": 0,
        "field": "description",
        "suggested_value": "Built FastAPI APIs.",
        "source_quote": "Built FastAPI APIs.",
        "confidence_label": "medium",
        "warnings": [],
    }


def test_build_confirmed_profile_save_payload_returns_none_without_confirmed_profile() -> None:
    payload = build_confirmed_profile_save_payload(
        resume_text="Skills: Python",
        baseline_review=_baseline_review(),
        confirmed_profile_result=None,
        accepted_suggestions=[],
        edited_suggestions=[],
        rejected_suggestions=[],
        missing_info_answers={},
    )

    assert payload is None


def test_build_confirmed_profile_save_payload_converts_suggestion_decisions() -> None:
    edited = _suggestion()
    edited["edited_value"] = "Edited FastAPI API evidence."

    payload = build_confirmed_profile_save_payload(
        resume_text="Skills: Python",
        baseline_review=_baseline_review(),
        confirmed_profile_result=_confirmed_profile_result(),
        accepted_suggestions=[_suggestion()],
        edited_suggestions=[edited],
        rejected_suggestions=[_suggestion()],
        missing_info_answers={},
    )

    statuses = [item["decision_status"] for item in payload["suggestion_decisions"]]
    assert statuses == ["accepted", "edited", "rejected"]
    assert payload["suggestion_decisions"][1]["edited_value"] == (
        "Edited FastAPI API evidence."
    )


def test_build_confirmed_profile_save_payload_filters_empty_missing_answers() -> None:
    payload = build_confirmed_profile_save_payload(
        resume_text="Skills: Python",
        baseline_review=_baseline_review(),
        confirmed_profile_result=_confirmed_profile_result(),
        accepted_suggestions=[],
        edited_suggestions=[],
        rejected_suggestions=[],
        missing_info_answers={
            "What role?": "Backend Engineer",
            "Empty answer": " ",
            "": "ignored",
        },
    )

    assert payload["missing_info_answers"] == [
        {"question": "What role?", "answer": "Backend Engineer"}
    ]


def test_build_confirmed_profile_save_payload_includes_core_fields_and_notes() -> None:
    payload = build_confirmed_profile_save_payload(
        resume_text="Skills: Python",
        baseline_review=_baseline_review(),
        confirmed_profile_result=_confirmed_profile_result(),
        accepted_suggestions=[],
        edited_suggestions=[],
        rejected_suggestions=[],
        missing_info_answers={},
        notes="Saved note",
    )

    assert payload["raw_resume_text"] == "Skills: Python"
    assert payload["baseline_profile"]
    assert payload["confirmed_result"]
    assert payload["notes"] == "Saved note"
