from __future__ import annotations

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_candidate_filter import filter_candidates
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate
from app.services.llm_service import LLMServiceError


class FakeFilterLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        return {"selected_indexes": [1, 0], "quality_warnings": []}


class FailingFilterLLM:
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
            "preferred_locations": ["Remote"],
            "work_arrangements": ["remote"],
            "strengths": ["Execution"],
            "risks": [],
            "missing_info_questions": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )


def _plan() -> JobSearchPlan:
    return JobSearchPlan(
        queries=["Backend Engineer Python FastAPI"],
        locations=["Remote"],
        target_roles=["Backend Engineer"],
        must_have_signals=["Python", "FastAPI"],
        avoid_signals=[],
        ranking_policy="Prefer backend overlap.",
        mode="deterministic",
    )


def _candidates() -> list[RawJobCandidate]:
    return [
        RawJobCandidate(
            title="Platform Engineer",
            company="Example A",
            location="Remote",
            source_url="https://example.com/a",
            source_provider="mock",
            snippet="Docker CI platform tooling.",
            raw_description="Docker CI platform tooling.",
        ),
        RawJobCandidate(
            title="Backend Engineer",
            company="Example B",
            location="Remote",
            source_url="https://example.com/b",
            source_provider="mock",
            snippet="Python FastAPI SQL APIs.",
            raw_description="Python FastAPI SQL APIs.",
        ),
    ]


def test_candidate_filter_llm_success_path() -> None:
    result = filter_candidates(
        _confirmed_profile(),
        _plan(),
        _candidates(),
        use_llm=True,
        llm_service=FakeFilterLLM(),
    )

    assert result.mode == "llm"
    assert result.selected_candidates[0].company == "Example B"


def test_candidate_filter_fallback_path() -> None:
    result = filter_candidates(
        _confirmed_profile(),
        _plan(),
        _candidates(),
        use_llm=True,
        llm_service=FailingFilterLLM(),
    )

    assert result.mode == "fallback"
    assert result.fallback_reason == "LLMServiceError"
    assert result.selected_candidates
