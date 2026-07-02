from __future__ import annotations

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_candidate_filter import filter_candidates
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate
from app.services.llm_service import LLMServiceError


class FakeFilterLLM:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return {
            "ranked_candidates": [
                {
                    "index": 1,
                    "match_score": 91,
                    "confidence_label": "strong",
                    "score_breakdown": {
                        "role_alignment": 25,
                        "domain_alignment": 18,
                        "skill_evidence": 18,
                        "seniority_and_work_type": 10,
                        "location_fit": 10,
                        "jd_evidence_quality": 10,
                        "risk_penalty": 0,
                    },
                    "matched_keywords": ["Python", "FastAPI", "SQL"],
                    "match_reasons": ["Strong backend role and stack overlap."],
                    "risks": [],
                    "evidence_quotes": ["Python FastAPI SQL APIs."],
                },
                {
                    "index": 0,
                    "match_score": 62,
                    "confidence_label": "limited",
                    "score_breakdown": {
                        "role_alignment": 12,
                        "domain_alignment": 8,
                        "skill_evidence": 8,
                        "seniority_and_work_type": 10,
                        "location_fit": 10,
                        "jd_evidence_quality": 10,
                        "risk_penalty": 0,
                    },
                    "matched_keywords": ["Docker"],
                    "match_reasons": ["Adjacent platform tooling overlap."],
                    "risks": ["Less direct backend API evidence."],
                    "evidence_quotes": ["Docker CI platform tooling."],
                },
            ],
            "quality_warnings": [],
        }


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
    llm = FakeFilterLLM()
    result = filter_candidates(
        _confirmed_profile(),
        _plan(),
        _candidates(),
        use_llm=True,
        llm_service=llm,
    )

    assert result.mode == "llm"
    assert result.selected_candidates[0].company == "Example B"
    assert result.scorecards[0].match_score == 91
    assert result.scorecards[0].score_breakdown["role_alignment"] == 25
    assert result.scorecards[0].evidence_quotes == ["Python FastAPI SQL APIs."]
    assert "Scoring rubric" in llm.system_prompt
    assert "break exact score ties by lower candidate index" in llm.system_prompt
    assert "Requested result limit" in llm.user_prompt


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
    assert result.scorecards
    assert result.scorecards[0].score_breakdown["role_alignment"] >= 20
    assert result.scorecards[0].score_breakdown["jd_evidence_quality"] > 0
    assert result.scorecards[0].evidence_quotes


def test_candidate_filter_deterministic_scorecard_prefers_role_and_domain_evidence() -> None:
    candidates = [
        RawJobCandidate(
            title="Python Developer",
            company="Generic Tools",
            location="Remote",
            source_url="https://example.com/tools",
            source_provider="mock",
            snippet="Python Docker SQL scripting for internal tools.",
            raw_description="Python Docker SQL scripting for internal tools.",
        ),
        RawJobCandidate(
            title="Backend Engineer",
            company="API Product",
            location="Remote",
            source_url="https://example.com/backend",
            source_provider="mock",
            snippet="Backend Engineer building FastAPI APIs and SQL-backed services for LLM applications.",
            raw_description="Backend Engineer building FastAPI APIs and SQL-backed services for LLM applications.",
        ),
    ]

    result = filter_candidates(
        _confirmed_profile(),
        _plan(),
        candidates,
        use_llm=False,
    )

    assert result.mode == "deterministic"
    assert result.selected_indexes[0] == 1
    top = result.scorecards[0]
    assert set(top.score_breakdown) == {
        "role_alignment",
        "domain_alignment",
        "skill_evidence",
        "seniority_and_work_type",
        "location_fit",
        "jd_evidence_quality",
        "risk_penalty",
    }
    assert top.score_breakdown["role_alignment"] == 25
    assert top.score_breakdown["domain_alignment"] > 0
    assert top.match_reasons
    assert top.evidence_quotes
