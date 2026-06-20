from __future__ import annotations

from app.schemas.resume import ProjectExperience, ResumeProfile
from app.services.llm_service import LLMServiceError
from app.services.resume_llm_review_service import build_guided_llm_resume_review
from app.services.resume_profile_review_service import build_resume_profile_review


class FakeResumeReviewLLM:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
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


class CorrectingResumeReviewLLM:
    def __init__(self) -> None:
        self.user_prompt = ""

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.user_prompt = user_prompt
        return {
            "resume_profile": {
                "raw_text": "Name: Mira Lee\nTarget Role: AI Agent Engineer\nSkills: Python",
                "name": "Mira Lee",
                "target_roles": ["AI Agent Engineer"],
                "education": [],
                "skills": ["Python"],
                "projects": [],
                "work_experiences": [],
                "certificates": [],
                "highlights": [],
                "missing_info": ["No project evidence found in raw resume."],
            },
            "quality_warnings": ["rejected unsupported deterministic project"],
        }


class FailingResumeReviewLLM:
    def __init__(self, message: str) -> None:
        self.message = message

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise LLMServiceError(self.message)


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

    assert review.analysis_mode == "llm_guided"
    assert review.parsed_profile.name == "Alex Chen"
    assert "AI Health Signal Processing Engineer" in review.parsed_profile.target_roles
    assert "physiological signal processing" in review.parsed_profile.skills
    assert review.parsed_profile.projects[0].name == "Wearable Health Signal Platform"


def test_guided_llm_receives_raw_resume_and_deterministic_profile() -> None:
    deterministic_profile = ResumeProfile(
        raw_text="Name: Alex Chen\nSkills: Python",
        name="Alex Chen",
        skills=["Python"],
    )
    service = FakeResumeReviewLLM()

    result = build_guided_llm_resume_review(
        raw_resume_text="Name: Alex Chen\nTarget Role: AI Health Engineer\nSkills: Python, PPG",
        deterministic_profile=deterministic_profile,
        llm_service=service,
    )

    assert result.analysis_mode == "llm_guided"
    assert "Target Role: AI Health Engineer" in service.user_prompt
    assert "Non-authoritative deterministic candidate profile JSON" in service.user_prompt
    assert '"skills": ["Python"]' in service.user_prompt
    assert "raw resume text is authoritative" in service.system_prompt.lower()


def test_guided_llm_preserves_explicit_target_role_from_raw_resume() -> None:
    review = build_resume_profile_review(
        "Name: Mira Lee\nTarget Role: AI Agent Engineer\nSkills: Python",
        use_llm=True,
        llm_service=CorrectingResumeReviewLLM(),
    )

    assert review.analysis_mode == "llm_guided"
    assert review.parsed_profile.target_roles == ["AI Agent Engineer"]


def test_guided_llm_can_reject_bad_deterministic_candidate() -> None:
    deterministic_profile = ResumeProfile(
        raw_text="Name: Mira Lee\nSkills: Python",
        name="Mira Lee",
        skills=["Python"],
        projects=[
            ProjectExperience(
                name="Unsupported Project",
                description="This came from a bad deterministic hint.",
                technologies=["Python"],
                highlights=[],
                raw_text="Unsupported Project",
            )
        ],
    )
    service = CorrectingResumeReviewLLM()

    result = build_guided_llm_resume_review(
        raw_resume_text="Name: Mira Lee\nTarget Role: AI Agent Engineer\nSkills: Python",
        deterministic_profile=deterministic_profile,
        llm_service=service,
    )

    assert result.analysis_mode == "llm_guided"
    assert "Unsupported Project" in service.user_prompt
    assert result.parsed_profile.projects == []
    assert "No project evidence found in raw resume." in result.parsed_profile.missing_info
    assert result.analysis_warnings == ["rejected unsupported deterministic project"]


def test_guided_llm_output_uses_production_resume_profile_schema() -> None:
    result = build_guided_llm_resume_review(
        raw_resume_text="Name: Alex Chen\nSkills: Python",
        deterministic_profile=ResumeProfile(raw_text="Name: Alex Chen\nSkills: Python"),
        llm_service=FakeResumeReviewLLM(),
    )

    assert isinstance(result.parsed_profile, ResumeProfile)
    assert result.parsed_profile.model_dump(mode="json")["work_experiences"] == []


def test_build_resume_profile_review_invalid_llm_json_falls_back() -> None:
    review = build_resume_profile_review(
        "Skills: Python\nProject: Built APIs.",
        use_llm=True,
        llm_service=InvalidResumeReviewLLM(),
    )

    assert review.analysis_mode == "fallback"
    assert review.analysis_warnings
    assert any("fallback triggered" in warning for warning in review.quality_warnings)


def test_build_resume_profile_review_fallback_warning_includes_safe_reason() -> None:
    review = build_resume_profile_review(
        "Skills: Python\nProject: Built APIs.",
        use_llm=True,
        llm_service=FailingResumeReviewLLM("DeepSeek provider is not configured."),
    )

    assert review.analysis_mode == "fallback"
    assert review.parsed_profile.skills == ["Python"]
    assert review.analysis_warnings == [
        "LLM resume analysis fallback triggered: LLMServiceError: "
        "DeepSeek provider is not configured."
    ]


def test_build_resume_profile_review_fallback_warning_masks_secrets() -> None:
    review = build_resume_profile_review(
        "Skills: Python\nProject: Built APIs.",
        use_llm=True,
        llm_service=FailingResumeReviewLLM(
            "Request failed with Bearer sk-live-secret-token-1234567890 "
            "DEEPSEEK_API_KEY=abc1234567890abcdef1234567890abcd "
            "token: zyxwvutsrqponmlkjihgfedcba987654321"
        ),
    )

    warning = review.analysis_warnings[0]
    assert "Bearer [masked]" in warning
    assert "DEEPSEEK_API_KEY=[masked]" in warning
    assert "token=[masked]" in warning
    assert "abc1234567890abcdef1234567890abcd" not in warning
    assert "zyxwvutsrqponmlkjihgfedcba987654321" not in warning


def test_build_resume_profile_review_unavailable_llm_falls_back() -> None:
    review = build_resume_profile_review(
        "Skills: Python\nProject: Built APIs.",
        use_llm=True,
        llm_service=None,
    )

    assert review.analysis_mode == "fallback"
    assert review.analysis_warnings == ["LLM resume analysis fallback triggered: llm_service_unavailable"]
