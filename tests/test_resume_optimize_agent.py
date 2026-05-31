from __future__ import annotations

from typing import Any

from app.agents.jd_analysis_agent import analyze_jd
from app.agents.match_agent import analyze_match
from app.agents.resume_optimize_agent import (
    optimize_resume,
    optimize_resume_with_llm,
    run_resume_optimize_agent,
)
from app.agents.resume_parse_agent import parse_resume
from app.schemas.match import ResumeOptimizationResult
from app.services.llm_service import LLMServiceError
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


class FakeLLMService:
    def __init__(self, payload: Any | None = None, should_fail: bool = False) -> None:
        self.payload = payload or {}
        self.should_fail = should_fail

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self.should_fail:
            raise LLMServiceError("fake invalid json")
        return self.payload  # type: ignore[return-value]


def _sample_inputs():
    resume_profile = parse_resume(SAMPLE_RESUME)
    job_analysis = analyze_jd(SAMPLE_JD)
    match_report = analyze_match(resume_profile, job_analysis)
    return resume_profile, job_analysis, match_report


def _valid_llm_payload() -> dict[str, Any]:
    return {
        "overall_issues": ["项目表达需要更清楚地对应 JD 的后端 API 能力。"],
        "keywords_to_add": ["REST API", "SQL"],
        "skills_section_suggestions": ["把 FastAPI、SQL、Pydantic 放在技能栏靠前位置。"],
        "project_rewrite_suggestions": [
            {
                "original": "JobAgent 求职分析工具",
                "suggestion": "围绕已有 JobAgent 项目，说明 API、schema 和测试职责。",
                "reason": "该建议只改写已有项目表达，不新增事实。",
            }
        ],
        "jd_targeted_bullets": ["基于已有项目补充 API 设计、数据流和测试覆盖说明。"],
        "do_not_exaggerate": ["不要新增没有真实使用过的技术栈或量化指标。"],
        "missing_info_needed": ["如有真实指标，可补充接口数量、测试数量或性能数据。"],
    }


def test_optimize_resume_mock_mode_returns_result() -> None:
    resume_profile, job_analysis, match_report = _sample_inputs()

    result = optimize_resume(SAMPLE_RESUME, resume_profile, job_analysis, match_report)

    assert isinstance(result, ResumeOptimizationResult)
    assert result.jd_targeted_bullets
    assert result.do_not_exaggerate


def test_run_resume_optimize_agent_defaults_to_mock_mode() -> None:
    resume_profile, job_analysis, match_report = _sample_inputs()

    result = run_resume_optimize_agent(
        SAMPLE_RESUME,
        resume_profile,
        job_analysis,
        match_report,
        use_llm=False,
    )

    assert result.metadata.mode == "mock"
    assert result.metadata.fallback_reason is None
    assert result.output.jd_targeted_bullets


def test_run_resume_optimize_agent_uses_llm_for_valid_payload() -> None:
    resume_profile, job_analysis, match_report = _sample_inputs()
    service = FakeLLMService(_valid_llm_payload())

    result = run_resume_optimize_agent(
        SAMPLE_RESUME,
        resume_profile,
        job_analysis,
        match_report,
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "llm"
    assert result.metadata.fallback_reason is None
    assert result.output.keywords_to_add == ["REST API", "SQL"]


def test_optimize_resume_with_llm_validates_structured_output() -> None:
    resume_profile, job_analysis, match_report = _sample_inputs()
    service = FakeLLMService(_valid_llm_payload())

    result = optimize_resume_with_llm(
        SAMPLE_RESUME,
        resume_profile,
        job_analysis,
        match_report,
        service=service,  # type: ignore[arg-type]
    )

    assert result.jd_targeted_bullets
    assert result.project_rewrite_suggestions[0].reason


def test_run_resume_optimize_agent_falls_back_when_llm_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("JOBAGENT_LLM_API_KEY", raising=False)
    resume_profile, job_analysis, match_report = _sample_inputs()

    result = run_resume_optimize_agent(
        SAMPLE_RESUME,
        resume_profile,
        job_analysis,
        match_report,
        use_llm=True,
    )

    assert result.metadata.mode == "fallback"
    assert result.metadata.fallback_reason == "LLMServiceError"
    assert result.output.jd_targeted_bullets


def test_run_resume_optimize_agent_falls_back_when_llm_returns_invalid_json() -> None:
    resume_profile, job_analysis, match_report = _sample_inputs()
    service = FakeLLMService(should_fail=True)

    result = run_resume_optimize_agent(
        SAMPLE_RESUME,
        resume_profile,
        job_analysis,
        match_report,
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "fallback"
    assert result.metadata.fallback_reason == "LLMServiceError"
    assert result.output.jd_targeted_bullets


def test_run_resume_optimize_agent_falls_back_when_llm_schema_invalid() -> None:
    resume_profile, job_analysis, match_report = _sample_inputs()
    service = FakeLLMService(
        {
            "project_rewrite_suggestions": [
                {
                    "original": "JobAgent 求职分析工具",
                }
            ]
        }
    )

    result = run_resume_optimize_agent(
        SAMPLE_RESUME,
        resume_profile,
        job_analysis,
        match_report,
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "fallback"
    assert result.metadata.fallback_reason == "ValidationError"
    assert result.output.jd_targeted_bullets
