from __future__ import annotations

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_candidate_filter import filter_candidates
from app.services.job_search_planner import (
    JobSearchPlan,
    build_structured_constraints,
)
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


def test_llm_filter_only_receives_pre_ranked_candidates_and_restores_original_index() -> None:
    class PreRankLLM:
        def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            assert user_prompt.count('"source_provider": "mock"') <= 30
            return {
                "ranked_candidates": [
                    {
                        "index": 0,
                        "match_score": 90,
                        "confidence_label": "strong",
                        "score_breakdown": {
                            "role_alignment": 25,
                            "domain_alignment": 20,
                            "skill_evidence": 15,
                            "seniority_and_work_type": 10,
                            "location_fit": 10,
                            "jd_evidence_quality": 10,
                            "risk_penalty": 0,
                        },
                        "matched_keywords": ["Backend Engineer"],
                        "match_reasons": ["Top deterministic pre-rank candidate."],
                        "risks": [],
                        "evidence_quotes": ["Backend Engineer Python FastAPI APIs"],
                    }
                ],
                "quality_warnings": [],
            }

    candidates = [
        RawJobCandidate(
            title="Unrelated Assistant",
            company=f"Example {index}",
            location="Remote",
            source_url=f"https://example.com/unrelated-{index}",
            source_provider="mock",
            snippet="General administrative work.",
            raw_description="General administrative work.",
        )
        for index in range(35)
    ]
    candidates.append(
        RawJobCandidate(
            title="Backend Engineer",
            company="Best Match",
            location="Remote",
            source_url="https://example.com/best",
            source_provider="mock",
            snippet="Backend Engineer Python FastAPI APIs",
            raw_description="Backend Engineer Python FastAPI APIs",
        )
    )

    result = filter_candidates(
        _confirmed_profile(),
        _plan(),
        candidates,
        use_llm=True,
        llm_service=PreRankLLM(),
        limit=10,
    )

    assert result.selected_indexes == [35]
    assert result.selected_candidates[0].company == "Best Match"
    assert result.diagnostics["payload_stats"]["pre_rank_candidate_count"] == 30


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


def test_hard_filter_rejects_explicit_mission_violations_before_ranking() -> None:
    plan = _plan().model_copy(
        update={
            "locations": ["Shenzhen"],
            "hard_constraints": ["只要深圳", "只考虑实习", "不要高级"],
            "excluded_roles": ["Sales"],
            "structured_constraints": build_structured_constraints(
                ["Shenzhen", "只考虑实习", "不要高级"],
                ["Sales"],
                ["Shenzhen"],
            ),
        }
    )

    def candidate(title: str, location: str | None, description: str) -> RawJobCandidate:
        return RawJobCandidate(
            title=title,
            company="Example",
            location=location,
            source_url=f"https://example.com/{title.replace(' ', '-').lower()}",
            source_provider="mock",
            snippet=description,
            raw_description=description,
        )

    candidates = [
        candidate("Backend Engineer Intern", "Shenzhen", "Python FastAPI internship."),
        candidate("Sales Intern", "Shenzhen", "Sales internship."),
        candidate("Senior Backend Engineer", "Shenzhen", "Senior engineering role."),
        candidate("Backend Engineer", "Shenzhen", "Full-time permanent role."),
        candidate("Backend Engineer Intern", "Beijing", "Python internship."),
        candidate("Backend Engineer Intern", "Shenzhen", "Job expired; internship closed."),
        candidate("Backend Engineer Intern", None, "Python internship."),
    ]

    result = filter_candidates(
        _confirmed_profile(),
        plan,
        candidates,
        use_llm=False,
        limit=10,
    )

    assert result.selected_indexes == [0, 6]
    assert {
        item["rejection_code"] for item in result.diagnostics["hard_filter"]["rejections"]
    } == {
        "excluded_role",
        "seniority_mismatch",
        "work_type_mismatch",
        "location_mismatch",
        "stale_listing",
    }
    hard_filter = result.diagnostics["hard_filter"]
    assert hard_filter["accepted_count"] == 1
    assert hard_filter["unknown_count"] == 1
    assert hard_filter["unknowns"][0]["unknown_fields"] == ("location",)


def test_candidate_filter_matches_boss_chinese_terms_and_location_aliases() -> None:
    profile = ConfirmedProfile.model_validate(
        {
            "confirmed_profile_id": "confirmed-health",
            "session_id": "session-health",
            "resume_document_id": "resume-health",
            "parsed_review_id": "review-health",
            "profile_draft_id": "draft-health",
            "summary": "AI health algorithm intern focused on physiological signals.",
            "target_roles": ["AI Health Algorithm Intern", "Physiological Signal Processing Intern"],
            "target_directions": ["AI health algorithms", "physiological signal processing"],
            "core_skills": ["PPG", "ECG", "PyTorch"],
            "supporting_skills": ["deep learning"],
            "search_keywords": ["AI health algorithm", "physiological signal processing", "PPG", "ECG"],
            "preferred_locations": ["Shenzhen", "China"],
            "work_arrangements": ["onsite"],
            "strengths": [],
            "risks": [],
            "missing_info_questions": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )
    plan = JobSearchPlan(
        locations=["Shenzhen"],
        target_roles=["AI Health Algorithm Intern", "Physiological Signal Processing Intern"],
        must_have_signals=["AI health algorithm", "physiological signal processing", "PPG", "ECG"],
        avoid_signals=[],
        ranking_policy="Prefer health algorithm and signal processing overlap.",
        mode="deterministic",
    )
    candidates = [
        RawJobCandidate(
            title="嵌入式开发实习生",
            company="Hardware Co",
            location="深圳 福田区",
            source_url="https://www.zhipin.com/job_detail/embedded.html",
            source_provider="boss_zhipin",
            snippet="C++ C 单片机 智能硬件 实习",
            raw_description="C++ C 单片机 智能硬件 实习",
            provider_warnings=[
                "Fetched via JobAgent Browser Helper; platform cookies were not sent to backend.",
            ],
        ),
        RawJobCandidate(
            title="AI算法实习生",
            company="Health AI Co",
            location="深圳 南山区",
            source_url="https://www.zhipin.com/job_detail/health-ai.html",
            source_provider="boss_zhipin",
            snippet="医疗健康 AI算法 生理信号 PPG ECG PyTorch 深度学习 实习",
            raw_description="医疗健康 AI算法 生理信号 PPG ECG PyTorch 深度学习 实习",
            provider_warnings=[
                "Fetched via JobAgent Browser Helper; platform cookies were not sent to backend.",
            ],
        ),
    ]

    result = filter_candidates(profile, plan, candidates, use_llm=False)

    assert result.selected_indexes[0] == 1
    top = result.scorecards[0]
    assert top.match_score >= 70
    assert top.score_breakdown["role_alignment"] >= 18
    assert top.score_breakdown["domain_alignment"] >= 18
    assert top.score_breakdown["location_fit"] == 10
    assert top.score_breakdown["risk_penalty"] == 0
