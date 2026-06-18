from __future__ import annotations

from app.services.resume_profile_review_service import build_resume_profile_review


class FakeResumeReviewLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return {
            "resume_profile": {
                "raw_text": "Name: Alex Chen\nAI health physiological signal processing",
                "name": "Alex Chen",
                "target_roles": ["AI Health Signal Processing Engineer"],
                "education": [],
                "skills": ["Python", "PPG", "ECG", "physiological signal processing"],
                "projects": [
                    {
                        "name": "Wearable Health Signal Platform",
                        "description": "Processed PPG and ECG signals for AI health analysis.",
                        "technologies": ["Python", "PPG", "ECG"],
                        "highlights": ["Built signal processing pipeline from resume evidence."],
                        "raw_text": "Wearable Health Signal Platform: PPG ECG Python",
                    }
                ],
                "work_experiences": [],
                "certificates": [],
                "highlights": ["AI health and physiological signal processing intent"],
                "missing_info": [],
            },
            "quality_warnings": [],
        }


class InvalidResumeReviewLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return {"resume_profile": {"name": 123, "skills": "not-a-list"}}


def test_build_resume_profile_review_use_llm_false_keeps_deterministic_mode() -> None:
    review = build_resume_profile_review(
        "Name: Jane Doe\nSkills: Python, FastAPI\nProject: Built APIs.",
        use_llm=False,
        llm_service=FakeResumeReviewLLM(),
    )

    assert review.analysis_mode == "deterministic"
    assert review.parsed_profile.name != "Alex Chen"


def test_build_resume_profile_review_with_fake_llm_improves_profile() -> None:
    review = build_resume_profile_review(
        "Name: Alex Chen\nInterested in AI health and physiological signal processing with PPG ECG.",
        use_llm=True,
        llm_service=FakeResumeReviewLLM(),
    )

    assert review.analysis_mode == "llm"
    assert review.parsed_profile.name == "Alex Chen"
    assert "AI Health Signal Processing Engineer" in review.parsed_profile.target_roles
    assert "physiological signal processing" in review.parsed_profile.skills
    assert review.parsed_profile.projects[0].name == "Wearable Health Signal Platform"


def test_build_resume_profile_review_invalid_llm_json_falls_back() -> None:
    review = build_resume_profile_review(
        "Skills: Python\nProject: Built APIs.",
        use_llm=True,
        llm_service=InvalidResumeReviewLLM(),
    )

    assert review.analysis_mode == "fallback"
    assert review.analysis_warnings
    assert any("fallback triggered" in warning for warning in review.quality_warnings)


def test_build_resume_profile_review_unavailable_llm_falls_back() -> None:
    review = build_resume_profile_review(
        "Skills: Python\nProject: Built APIs.",
        use_llm=True,
        llm_service=None,
    )

    assert review.analysis_mode == "fallback"
    assert review.analysis_warnings == ["LLM resume analysis fallback triggered: llm_service_unavailable"]
