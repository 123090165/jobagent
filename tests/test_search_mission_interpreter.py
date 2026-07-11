from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.search_mission import SearchMissionInput
from app.services.search_mission_interpreter import interpret_search_mission


def _profile() -> ConfirmedProfile:
    return ConfirmedProfile.model_validate(
        {
            "confirmed_profile_id": "profile-1",
            "session_id": "session-1",
            "resume_document_id": "resume-1",
            "parsed_review_id": "review-1",
            "profile_draft_id": "draft-1",
            "summary": "Backend engineer building Python APIs.",
            "target_roles": ["Backend Engineer"],
            "target_directions": ["AI Application Engineer"],
            "core_skills": ["Python", "FastAPI"],
            "supporting_skills": ["SQL"],
            "search_keywords": ["backend"],
            "preferred_locations": [],
            "work_arrangements": [],
            "strengths": [],
            "risks": [],
            "missing_info_questions": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )


class BrokenLlm:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise RuntimeError("provider unavailable")


def test_interpreter_detects_conflicts_without_llm() -> None:
    result, mode, fallback = interpret_search_mission(
        SearchMissionInput(
            target_roles=["Research Scientist"],
            excluded_roles=["Research Scientist"],
            must_have=["PyTorch research"],
        ),
        _profile(),
    )

    assert mode == "deterministic"
    assert fallback is None
    assert result.conflicts
    assert 1 <= len(result.clarification_questions) <= 3


def test_interpreter_falls_back_when_llm_fails() -> None:
    result, mode, fallback = interpret_search_mission(
        SearchMissionInput(target_roles=["Backend Engineer"]),
        _profile(),
        llm_service=BrokenLlm(),
    )

    assert mode == "fallback"
    assert fallback == "provider unavailable"
    assert result.target_roles == ["Backend Engineer"]
