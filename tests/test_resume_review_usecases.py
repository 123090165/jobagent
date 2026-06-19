from __future__ import annotations

from app.application.resume_review_usecases import parse_resume_for_review
from app.application.profile_session_usecases import create_profile_session
from app.application.resume_intake_usecases import submit_resume_text


class FakeResumeReviewLLM:
    def __init__(self, *, name: str = "Alex Chen") -> None:
        self.name = name
        self.calls = 0

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.calls += 1
        return {
            "resume_profile": {
                "raw_text": "Name: Alex Chen\nAI health physiological signal processing",
                "name": self.name,
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


class FailingIfCalledLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise AssertionError("LLM service should not be called")


def test_parse_resume_for_review_stores_final_llm_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "resume-review-usecase.sqlite3"))
    session = create_profile_session()
    submit_resume_text(
        session.session_id,
        "Name: Alex Chen\nInterested in AI health and physiological signal processing with PPG ECG.",
    )

    response = parse_resume_for_review(
        session.session_id,
        regenerate=True,
        use_llm=True,
        llm_service=FakeResumeReviewLLM(),
    )

    review = response.parsed_review
    assert review.analysis_mode == "llm"
    assert review.raw_parser_output is not None
    assert review.raw_parser_output["name"] == "Alex Chen"
    assert "AI Health Signal Processing Engineer" in review.raw_parser_output["target_roles"]
    assert "AI Health Signal Processing Engineer" in review.target_signals


def test_deterministic_cached_review_does_not_block_llm_run(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "resume-review-cache.sqlite3"))
    session = create_profile_session()
    submit_resume_text(
        session.session_id,
        "Name: Alex Chen\nSkills: Python\nProject: Built a FastAPI parser.",
    )
    deterministic_response = parse_resume_for_review(
        session.session_id,
        regenerate=True,
        use_llm=False,
    )
    service = FakeResumeReviewLLM(name="LLM Alex")

    llm_response = parse_resume_for_review(
        session.session_id,
        regenerate=False,
        use_llm=True,
        llm_service=service,
    )

    assert deterministic_response.parsed_review.analysis_mode == "deterministic"
    assert llm_response.parsed_review.analysis_mode == "llm"
    assert llm_response.parsed_review.parsed_review_id != (
        deterministic_response.parsed_review.parsed_review_id
    )
    assert llm_response.parsed_review.basic_info["name"] == "LLM Alex"
    assert service.calls == 1


def test_existing_llm_review_can_be_reused_without_regenerate(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "resume-review-llm-cache.sqlite3"))
    session = create_profile_session()
    submit_resume_text(
        session.session_id,
        "Name: Alex Chen\nSkills: Python\nProject: Built a FastAPI parser.",
    )
    first = parse_resume_for_review(
        session.session_id,
        regenerate=True,
        use_llm=True,
        llm_service=FakeResumeReviewLLM(name="Cached Alex"),
    )

    second = parse_resume_for_review(
        session.session_id,
        regenerate=False,
        use_llm=True,
        llm_service=FailingIfCalledLLM(),  # type: ignore[arg-type]
    )

    assert second.parsed_review.parsed_review_id == first.parsed_review.parsed_review_id
    assert second.parsed_review.analysis_mode == "llm"
    assert second.parsed_review.basic_info["name"] == "Cached Alex"


def test_regenerate_bypasses_existing_llm_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "resume-review-regenerate.sqlite3"))
    session = create_profile_session()
    submit_resume_text(
        session.session_id,
        "Name: Alex Chen\nSkills: Python\nProject: Built a FastAPI parser.",
    )
    first = parse_resume_for_review(
        session.session_id,
        regenerate=True,
        use_llm=True,
        llm_service=FakeResumeReviewLLM(name="First Alex"),
    )
    service = FakeResumeReviewLLM(name="Regenerated Alex")

    second = parse_resume_for_review(
        session.session_id,
        regenerate=True,
        use_llm=True,
        llm_service=service,
    )

    assert second.parsed_review.parsed_review_id != first.parsed_review.parsed_review_id
    assert second.parsed_review.analysis_mode == "llm"
    assert second.parsed_review.basic_info["name"] == "Regenerated Alex"
    assert service.calls == 1
