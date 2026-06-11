from __future__ import annotations

from frontend.profile_review_state import (
    apply_suggestion_to_profile_draft,
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
