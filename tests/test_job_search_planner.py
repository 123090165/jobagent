from __future__ import annotations

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_search_planner import build_search_plan
from app.services.llm_service import LLMServiceError


class FakePlannerLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return {
            "queries": ["Backend Engineer Python FastAPI", "Platform Engineer Docker Python"],
            "locations": ["Remote", "Tokyo"],
            "target_roles": ["Backend Engineer", "Platform Engineer"],
            "must_have_signals": ["Python", "FastAPI", "Docker"],
            "avoid_signals": ["onsite only"],
            "ranking_policy": "Prefer backend API work with platform depth.",
            "quality_warnings": [],
        }


class FailingPlannerLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise LLMServiceError("boom")


def _confirmed_profile() -> ConfirmedProfile:
    return ConfirmedProfile.model_validate(
        {
            "confirmed_profile_id": "confirmed-1",
            "session_id": "session-1",
            "resume_document_id": "resume-1",
            "parsed_review_id": "review-1",
            "profile_draft_id": "draft-1",
            "summary": "Backend-focused engineer with applied AI interests.",
            "target_roles": ["Backend Engineer"],
            "target_directions": ["Platform", "AI applications"],
            "core_skills": ["Python", "FastAPI", "SQL"],
            "supporting_skills": ["Docker"],
            "search_keywords": ["APIs", "LLM applications"],
            "preferred_locations": ["Remote", "Tokyo"],
            "work_arrangements": ["remote"],
            "strengths": ["Execution"],
            "risks": ["onsite only"],
            "missing_info_questions": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )


def test_job_search_planner_llm_success_path() -> None:
    plan = build_search_plan(_confirmed_profile(), use_llm=True, llm_service=FakePlannerLLM())

    assert plan.mode == "llm"
    assert "Backend Engineer Python FastAPI" in plan.queries
    assert "Python" in plan.must_have_signals


def test_job_search_planner_fallback_path() -> None:
    plan = build_search_plan(_confirmed_profile(), use_llm=True, llm_service=FailingPlannerLLM())

    assert plan.mode == "fallback"
    assert plan.fallback_reason == "LLMServiceError"
    assert plan.queries
