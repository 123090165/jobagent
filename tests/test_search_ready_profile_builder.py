from __future__ import annotations

from app.services.resume_profile_review_service import build_resume_profile_review
from app.services.search_ready_profile_builder import build_search_ready_profile
from tests.fixtures.resumes.profile_review_quality_cases import PROFILE_REVIEW_QUALITY_CASES


def _case(case_id: str):
    return next(case for case in PROFILE_REVIEW_QUALITY_CASES if case.case_id == case_id)


def _build(case_id: str):
    case = _case(case_id)
    review = build_resume_profile_review(case.resume_text, target_roles=case.target_roles)
    return build_search_ready_profile(
        review.parsed_profile,
        case.target_roles,
        quality_warnings=review.quality_warnings,
        missing_info_questions=review.missing_info_questions,
    )


def test_anker_ai_health_builds_search_ready_profile() -> None:
    profile = _build("anker_ai_health_algorithm")
    combined = " ".join(
        [profile.summary, *profile.target_directions, *profile.core_skills, *profile.search_keywords]
    ).lower()

    assert "ai health algorithm intern" in [item.lower() for item in profile.target_directions]
    assert "physiological signal processing" in combined
    assert "ppg" in combined
    assert "ecg" in combined
    assert "wearable health monitoring" in combined


def test_business_fa_builds_research_profile() -> None:
    profile = _build("realistic_business_resume_unstructured")
    combined = " ".join([*profile.core_skills, *profile.search_keywords]).lower()

    assert "business analyst" in [item.lower() for item in profile.target_directions]
    assert "investment analyst" in [item.lower() for item in profile.target_directions]
    assert "industry research" in profile.core_skills
    assert "market research" in profile.core_skills
    assert "competitor analysis" in profile.core_skills
    assert "meeting notes" in profile.core_skills
    assert "crm" in combined
    assert "wind" in combined
    assert "企查查" in profile.auxiliary_skills
    assert "Wind" in profile.auxiliary_skills
    assert "Excel" in profile.auxiliary_skills
    assert "PowerPoint" in profile.auxiliary_skills
    assert "CRM" in profile.auxiliary_skills


def test_business_keywords_preserve_qichacha_without_garbled_text() -> None:
    profile = _build("realistic_business_resume_unstructured")

    assert "企查查" in profile.search_keywords
    assert all("浼佹煡鏌" not in keyword for keyword in profile.search_keywords)
    assert all("?" not in keyword for keyword in profile.search_keywords if "企查查" in keyword)


def test_ai_agent_backend_builds_agent_search_profile() -> None:
    profile = _build("ai_agent_backend")
    combined = " ".join([profile.summary, *profile.core_skills, *profile.search_keywords]).lower()

    assert "ai agent engineer" in [item.lower() for item in profile.target_directions]
    assert "fastapi" in combined
    assert "langgraph" in combined or "langchain" in combined
    assert "backend api" in combined
    assert "evaluation / testing" in combined


def test_weak_resume_is_not_overexpanded() -> None:
    profile = _build("weak_resume")

    assert profile.target_directions == []
    assert len(profile.core_skills) <= 1
    assert profile.company_preferences == []
    assert profile.missing_info_questions


def test_search_keywords_are_deduped() -> None:
    profile = _build("ml_audio_asr")

    lowered = [item.lower() for item in profile.search_keywords]
    assert len(lowered) == len(set(lowered))


def test_business_search_keywords_are_deduped_after_normalization() -> None:
    profile = _build("realistic_business_resume_unstructured")

    lowered = [item.lower() for item in profile.search_keywords]
    assert len(lowered) == len(set(lowered))


def test_core_and_auxiliary_skills_do_not_fully_overlap() -> None:
    profile = _build("embedded_stm32")

    assert not (set(profile.core_skills) & set(profile.auxiliary_skills))


def test_preferred_locations_are_extracted() -> None:
    ai_health = _build("anker_ai_health_algorithm")

    assert "Shenzhen" in ai_health.preferred_locations
