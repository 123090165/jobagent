"""回归验证职位搜索 run、结果与 trace的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from threading import Barrier

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_search_planner import build_search_plan
from app.services.job_search_execution.provider_search import (
    _run_provider_search,
    build_provider_search_tasks,
    candidate_pool_cap_for,
    select_provider_queries,
)
from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_providers.multi_source_provider import (
    MultiSourceJobSearchProvider,
)
from app.services.llm_service import LLMServiceError
from app.services.search_signal_normalizer import build_bilingual_search_signals


class FakePlannerLLM:
    """为当前测试场景提供 FakePlannerLLM 夹具或替身。"""
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        """提供 FakePlannerLLM.chat_completion_json 所需的测试行为。"""
        return {
            "role_titles": ["Backend Engineer", "Platform Engineer"],
            "role_families": ["engineering"],
            "industry_domains": ["Platform", "AI applications"],
            "evidence_skills": ["APIs", "LLM applications"],
            "generic_tools": ["Python", "FastAPI", "Docker"],
            "constraints": ["Remote", "Tokyo"],
            "negative_signals": ["onsite only"],
            "broad_queries": ["Backend Engineer", "Platform Engineer"],
            "domain_queries": ["Backend Engineer Platform"],
            "evidence_queries": ["Backend Engineer APIs LLM applications"],
            "tool_queries": ["Backend Engineer Python FastAPI"],
            "quality_warnings": [],
        }


class FailingPlannerLLM:
    """为当前测试场景提供 FailingPlannerLLM 夹具或替身。"""
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        """提供 FailingPlannerLLM.chat_completion_json 所需的测试行为。"""
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
    assert plan.search_intent is not None
    assert plan.search_intent.role_families == ["engineering"]
    assert {item.query_type for item in plan.planned_queries} >= {
        "broad",
        "role_domain",
        "evidence",
        "tool",
    }


def test_query_selector_balances_query_types_instead_of_taking_first_three() -> None:
    plan = build_search_plan(_confirmed_profile(), use_llm=True, llm_service=FakePlannerLLM())

    selected = select_provider_queries(plan)

    assert len(selected) == 5
    assert [item.query_type for item in selected] == [
        "role_domain",
        "evidence",
        "broad",
        "tool",
        "broad",
    ]
    assert "Backend Engineer APIs LLM applications" in [item.query for item in selected]


def test_candidate_recall_pool_is_large_but_bounded() -> None:
    assert candidate_pool_cap_for(5) == 30
    assert candidate_pool_cap_for(10) == 60
    assert candidate_pool_cap_for(20) == 100


def test_provider_tasks_translate_queries_and_cover_sources_and_locations() -> None:
    class SourceProvider:
        provider_kind = "test"

        def __init__(self, provider_name: str) -> None:
            self.provider_name = provider_name

        def search_jobs(self, *, query: str, location: str | None, limit: int):
            return []

    provider = MultiSourceJobSearchProvider(
        [
            SourceProvider("cuhksz_career"),
            SourceProvider("linkedin"),
            SourceProvider("remoteok"),
        ]
    )
    plan = build_search_plan(
        _confirmed_profile(),
        use_llm=True,
        llm_service=FakePlannerLLM(),
    )

    tasks = build_provider_search_tasks(provider, search_plan=plan, per_call_limit=5)
    by_source = {
        source: [task for task in tasks if task.source == source]
        for source in provider.source_names
    }

    assert [task.source for task in tasks[:3]] == provider.source_names
    assert all(task.location is None for task in by_source["cuhksz_career"])
    assert all(
        task.planned_query.query not in plan.queries
        for task in by_source["cuhksz_career"]
    )
    assert {task.location for task in by_source["linkedin"]} == {"Remote", "Tokyo"}
    assert all(task.planned_query.query_type != "tool" for task in by_source["linkedin"])
    assert len(by_source["remoteok"]) == 1
    assert by_source["remoteok"][0].planned_query.query_type == "broad"


def test_multi_source_recall_runs_sources_concurrently_and_merges_in_task_order() -> None:
    barrier = Barrier(2)

    class ConcurrentSourceProvider:
        provider_kind = "test"

        def __init__(self, provider_name: str) -> None:
            self.provider_name = provider_name
            self.calls = 0

        def search_jobs(self, *, query: str, location: str | None, limit: int):
            self.calls += 1
            if self.calls == 1:
                barrier.wait(timeout=1)
            return [
                RawJobCandidate(
                    title=f"{self.provider_name} Backend Engineer",
                    company=self.provider_name,
                    location=location,
                    source_url=f"https://example.com/{self.provider_name}/{self.calls}",
                    source_provider=self.provider_name,
                    snippet="Backend engineering role.",
                )
            ]

    provider = MultiSourceJobSearchProvider(
        [
            ConcurrentSourceProvider("linkedin"),
            ConcurrentSourceProvider("remoteok"),
        ]
    )
    plan = build_search_plan(
        _confirmed_profile(),
        use_llm=True,
        llm_service=FakePlannerLLM(),
    )

    result = _run_provider_search(provider, search_plan=plan, max_results=5)

    assert [stat.source for stat in result.query_stats[:2]] == ["linkedin", "remoteok"]
    assert {candidate.source_provider for candidate in result.candidates} == {
        "linkedin",
        "remoteok",
    }
    assert result.details()["source_execution_mode"] == "bounded_parallel"
    assert result.details()["source_concurrency"] == 2


def test_job_search_planner_fallback_path() -> None:
    plan = build_search_plan(_confirmed_profile(), use_llm=True, llm_service=FailingPlannerLLM())

    assert plan.mode == "fallback"
    assert plan.fallback_reason == "LLMServiceError"
    assert plan.queries


def test_build_bilingual_search_signals_expands_chinese_aliases() -> None:
    signals = build_bilingual_search_signals(
        target_roles=[],
        keywords=["语音识别", "生理信号处理", "可穿戴健康"],
        core_skills=["PPG", "ECG"],
    )

    assert "语音识别" in signals["zh_terms"]
    assert "speech recognition" in signals["en_terms"]
    assert "ASR" in signals["normalized_signals"]
    assert "physiological signal processing" in signals["en_terms"]
    assert "wearable health" in signals["en_terms"]
    assert "PPG" in signals["normalized_signals"]
    assert "ECG" in signals["normalized_signals"]


def test_deterministic_plan_keeps_bilingual_signals_for_future_english_sources() -> None:
    profile = _confirmed_profile().model_copy(
        update={
            "target_roles": ["后端工程师"],
            "search_keywords": ["语音识别"],
            "core_skills": ["Python", "ASR"],
        }
    )

    plan = build_search_plan(profile, use_llm=False)

    assert plan.mode == "deterministic"
    assert "语音识别" in " ".join(plan.queries)
    assert "ASR" in plan.must_have_signals
    assert "profile-derived role overlap" in plan.ranking_policy


def test_deterministic_plan_uses_focused_provider_queries_for_health_algorithm() -> None:
    profile = _confirmed_profile().model_copy(
        update={
            "summary": "健康算法方向，侧重生理信号和可穿戴健康。",
            "target_roles": ["健康算法实习生", "生理信号算法实习生"],
            "target_directions": ["医疗 AI", "可穿戴健康"],
            "search_keywords": ["生理信号处理", "PPG", "ECG", "可穿戴健康"],
            "core_skills": ["Python", "MATLAB", "PyTorch"],
        }
    )

    plan = build_search_plan(profile, use_llm=False)

    assert plan.queries[0] == "健康算法实习生"
    assert any("健康算法实习生" in query and "PPG" in query for query in plan.queries)
    assert any("生理信号算法实习生" in query and "PPG" in query for query in plan.queries)
    assert "Python" not in plan.queries[0]
    assert "MATLAB" not in plan.queries[0]
    assert "PPG" in plan.must_have_signals
    assert "ECG" in plan.must_have_signals
