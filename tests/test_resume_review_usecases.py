from __future__ import annotations

from app.application.resume_review_usecases import parse_resume_for_review
from app.application.profile_session_usecases import create_profile_session
from app.application.resume_intake_usecases import submit_resume_text


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
