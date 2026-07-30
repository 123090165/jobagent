"""回归验证画像草稿的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from app.schemas.profile_draft import ProfileDraft
from app.services.profile_draft_service import (
    answer_missing_info_question,
    confirm_profile_draft,
    create_profile_draft,
    update_profile_draft,
)
from app.services.resume_profile_review_service import build_resume_profile_review
from tests.fixtures.resumes.profile_review_quality_cases import PROFILE_REVIEW_QUALITY_CASES


def _case(case_id: str):
    return next(case for case in PROFILE_REVIEW_QUALITY_CASES if case.case_id == case_id)


def _create(case_id: str) -> ProfileDraft:
    case = _case(case_id)
    review = build_resume_profile_review(case.resume_text, target_roles=case.target_roles)
    return create_profile_draft(
        review.parsed_profile,
        case.target_roles,
        quality_warnings=review.quality_warnings,
        missing_info_questions=review.missing_info_questions,
    )


def test_create_profile_draft_builds_search_ready_profile() -> None:
    draft = _create("anker_ai_health_algorithm")

    assert draft.status == "draft"
    assert draft.llm_provider == "deepseek"
    assert draft.search_ready_profile.target_directions
    assert "PPG" in draft.search_ready_profile.search_keywords
    assert draft.source_profile_snapshot


def test_create_profile_draft_accepts_deepseek_provider(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    case = _case("ai_agent_backend")
    review = build_resume_profile_review(case.resume_text, target_roles=case.target_roles)

    draft = create_profile_draft(
        review.parsed_profile,
        case.target_roles,
        quality_warnings=review.quality_warnings,
        missing_info_questions=review.missing_info_questions,
        llm_provider="deepseek",
    )

    assert draft.llm_provider == "deepseek"
    assert draft.llm_configured is False
    assert draft.llm_provider_reason


def test_update_profile_draft_updates_summary() -> None:
    draft = _create("ai_agent_backend")

    updated = update_profile_draft(draft, {"summary": "Focused backend and agent profile."})

    assert updated.search_ready_profile.summary == "Focused backend and agent profile."
    assert updated.user_edit_snapshot["summary"] == "Focused backend and agent profile."


def test_update_profile_draft_updates_list_fields() -> None:
    draft = _create("realistic_business_resume_unstructured")

    updated = update_profile_draft(
        draft,
        {
            "target_directions": ["Business Analyst", "business analyst", "", "FA Intern"],
            "core_skills": ["industry research", "market research", "industry research"],
            "auxiliary_skills": ["Wind", "企查查", "Wind"],
            "search_keywords": ["企查查", "Wind", "", "FA Intern"],
        },
    )

    assert updated.search_ready_profile.target_directions == ["Business Analyst", "FA Intern"]
    assert updated.search_ready_profile.core_skills == ["industry research", "market research"]
    assert updated.search_ready_profile.auxiliary_skills == ["Wind", "企查查"]
    assert updated.search_ready_profile.search_keywords == ["企查查", "Wind", "FA Intern"]


def test_answer_missing_info_question_persists_user_answer() -> None:
    draft = _create("weak_resume")
    question = draft.search_ready_profile.missing_info_questions[0]

    updated = answer_missing_info_question(draft, question, "Backend Engineer")

    assert updated.user_answers[question] == "Backend Engineer"
    assert any("Backend Engineer" in note for note in updated.search_ready_profile.profile_notes)


def test_confirm_profile_draft_returns_payload() -> None:
    draft = _create("ai_agent_backend")

    payload = confirm_profile_draft(draft)

    assert payload["status"] == "confirmed"
    assert payload["confirmed_search_ready_profile"]["summary"]
    assert payload["source_profile_snapshot"]
    assert payload["missing_info_answers"] == {}
    assert payload["llm_provider_metadata"]["provider"] == "deepseek"
    assert payload["save_payload_ready"] is True


def test_weak_resume_draft_is_not_auto_expanded() -> None:
    draft = _create("weak_resume")

    assert draft.search_ready_profile.target_directions == []
    assert draft.search_ready_profile.core_skills == []
    assert "strong" not in draft.search_ready_profile.summary.lower()
