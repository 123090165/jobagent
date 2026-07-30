"""回归验证画像草稿的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.profile_draft_usecases import _build_profile_draft_seed
from app.application.resume_review_usecases import _build_target_signals
from app.schemas.parsed_resume_review import ParsedResumeReview
from app.services.resume_profile_review_service import build_resume_profile_review
from tests.fixtures.resumes.profile_review_quality_cases import PROFILE_REVIEW_QUALITY_CASES


def _case(case_id: str):
    return next(case for case in PROFILE_REVIEW_QUALITY_CASES if case.case_id == case_id)


def _draft_seed_for_case(case_id: str) -> dict[str, object]:
    case = _case(case_id)
    review = build_resume_profile_review(case.resume_text, target_roles=case.target_roles)
    profile = review.parsed_profile
    parsed_review = ParsedResumeReview(
        parsed_review_id=f"{case_id}-review",
        session_id=f"{case_id}-session",
        resume_document_id=f"{case_id}-resume",
        basic_info={
            "name": profile.name,
            "highlights": profile.highlights,
            "certificates": profile.certificates,
        },
        education=[item.model_dump(mode="json") for item in profile.education],
        work_experience=[item.model_dump(mode="json") for item in profile.work_experiences],
        projects=[item.model_dump(mode="json") for item in profile.projects],
        skills={"items": profile.skills, "count": len(profile.skills)},
        target_signals=_build_target_signals(profile),
        quality_warnings=review.quality_warnings,
        missing_info_questions=review.missing_info_questions,
        raw_parser_output=profile.model_dump(mode="json"),
        analysis_mode=review.analysis_mode,
        analysis_provider=review.analysis_provider,
        analysis_warnings=review.analysis_warnings,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return _build_profile_draft_seed(parsed_review)


def test_profile_draft_seed_keeps_health_algorithm_focus() -> None:
    seed = _draft_seed_for_case("anker_ai_health_algorithm")

    roles = seed["target_roles"]
    assert roles == [
        "AI Health Algorithm Intern",
        "Physiological Signal Processing Intern",
        "Biomedical AI Intern",
    ]
    assert "Backend Engineer" not in roles
    assert "Embedded Software Engineer" not in roles
    assert "AI Application Engineer" not in roles
    assert seed["target_directions"] == [
        "AI health algorithms and physiological signal processing"
    ]

    core_skills = seed["core_skills"]
    assert core_skills[:3] == ["PPG", "ECG", "ACC"]
    assert "physiological signal processing" in core_skills
    assert "Python" not in core_skills[:8]
    assert "PPG" in seed["search_keywords"]
    assert "ECG" in seed["search_keywords"]


def test_profile_draft_seed_keeps_backend_agent_focus() -> None:
    seed = _draft_seed_for_case("ai_agent_backend")

    assert "Backend Engineer" in seed["target_roles"]
    assert "AI Application Engineer" in seed["target_roles"]
    assert "AI Health Algorithm Intern" not in seed["target_roles"]
    assert "FastAPI" in seed["core_skills"]
    assert "LangGraph" in seed["search_keywords"]
