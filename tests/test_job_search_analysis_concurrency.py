from __future__ import annotations

import threading
import time

from app.agents.types import AgentRunMetadata, AgentRunResult
from app.application import job_search_usecases
from app.schemas.job import JobAnalysis
from app.services.job_candidate_filter import CandidateFilterResult
from app.services.job_search_execution import candidate_analysis
from app.services.job_search_providers.base import RawJobCandidate


def _candidate(label: str) -> RawJobCandidate:
    return RawJobCandidate(
        title=label,
        company="Example",
        location="Remote",
        source_url=f"https://example.test/{label}",
        source_provider="test",
        snippet=label,
        raw_description=label,
    )


def _filter_result(labels: list[str]) -> CandidateFilterResult:
    return CandidateFilterResult(
        selected_candidates=[_candidate(label) for label in labels],
        selected_indexes=list(range(len(labels))),
        scorecards=[],
        mode="deterministic",
    )


def test_jd_analysis_uses_bounded_parallelism(monkeypatch) -> None:
    active_count = 0
    max_active_count = 0
    lock = threading.Lock()

    def fake_run_jd_analysis_agent(text: str, *, use_llm: bool, service: object | None = None):
        nonlocal active_count, max_active_count
        with lock:
            active_count += 1
            max_active_count = max(max_active_count, active_count)
        try:
            time.sleep(0.05)
            return AgentRunResult(
                output=JobAnalysis(raw_jd=text, job_title=text, keywords=[text]),
                metadata=AgentRunMetadata(
                    agent_name="JDAnalysisAgent",
                    mode="llm" if use_llm else "mock",
                    guardrails=["test-guardrail"],
                ),
            )
        finally:
            with lock:
                active_count -= 1

    monkeypatch.setenv("JOBAGENT_JD_ANALYSIS_CONCURRENCY", "3")
    monkeypatch.setattr(
        candidate_analysis,
        "run_jd_analysis_agent",
        fake_run_jd_analysis_agent,
    )

    result = job_search_usecases._analyze_candidates(
        _filter_result(["first", "second", "third"]),
        use_llm=True,
        llm_service=None,
    )

    assert max_active_count > 1
    assert result["concurrency"] == 3
    assert result["fallback_count"] == 0
    assert result["mode_counts"] == {"llm": 3}
    assert [item["analysis"].raw_jd for item in result["items"]] == ["first", "second", "third"]


def test_jd_analysis_concurrency_one_preserves_serial_behavior(monkeypatch) -> None:
    active_count = 0
    max_active_count = 0
    lock = threading.Lock()

    def fake_run_jd_analysis_agent(text: str, *, use_llm: bool, service: object | None = None):
        nonlocal active_count, max_active_count
        with lock:
            active_count += 1
            max_active_count = max(max_active_count, active_count)
        try:
            time.sleep(0.01)
            return AgentRunResult(
                output=JobAnalysis(raw_jd=text, job_title=text, keywords=[text]),
                metadata=AgentRunMetadata(
                    agent_name="JDAnalysisAgent",
                    mode="llm" if use_llm else "mock",
                ),
            )
        finally:
            with lock:
                active_count -= 1

    monkeypatch.setenv("JOBAGENT_JD_ANALYSIS_CONCURRENCY", "1")
    monkeypatch.setattr(
        candidate_analysis,
        "run_jd_analysis_agent",
        fake_run_jd_analysis_agent,
    )

    result = job_search_usecases._analyze_candidates(
        _filter_result(["first", "second", "third"]),
        use_llm=True,
        llm_service=None,
    )

    assert max_active_count == 1
    assert result["concurrency"] == 1
    assert [item["analysis"].raw_jd for item in result["items"]] == ["first", "second", "third"]


def test_jd_analysis_parallel_failure_falls_back_per_candidate(monkeypatch) -> None:
    def fake_run_jd_analysis_agent(text: str, *, use_llm: bool, service: object | None = None):
        if use_llm and text == "bad":
            raise RuntimeError("bad candidate")
        return AgentRunResult(
            output=JobAnalysis(raw_jd=text, job_title=text, keywords=[text]),
            metadata=AgentRunMetadata(
                agent_name="JDAnalysisAgent",
                mode="llm" if use_llm else "mock",
            ),
        )

    monkeypatch.setenv("JOBAGENT_JD_ANALYSIS_CONCURRENCY", "3")
    monkeypatch.setattr(
        candidate_analysis,
        "run_jd_analysis_agent",
        fake_run_jd_analysis_agent,
    )

    result = job_search_usecases._analyze_candidates(
        _filter_result(["first", "bad", "third"]),
        use_llm=True,
        llm_service=None,
    )

    assert [item["analysis"].raw_jd for item in result["items"]] == ["first", "bad", "third"]
    assert [item["analysis_mode"] for item in result["items"]] == ["llm", "fallback", "llm"]
    assert result["fallback_count"] == 1
    assert result["fallback_reason"] == "RuntimeError"
    assert "JD analysis fallback triggered: RuntimeError." in result["quality_warnings"]
