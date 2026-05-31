from __future__ import annotations

from typing import Any

from app.agents.jd_analysis_agent import analyze_jd
from app.agents.project_challenge_agent import (
    generate_project_challenge_with_llm,
    generate_project_challenges,
    run_project_challenge_agent,
)
from app.agents.resume_parse_agent import parse_resume
from app.schemas.match import ProjectChallengeReport
from app.services.llm_service import LLMServiceError
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


class FakeLLMService:
    def __init__(self, payload: Any | None = None, should_fail: bool = False) -> None:
        self.payload = payload or {}
        self.should_fail = should_fail

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self.should_fail:
            raise LLMServiceError("fake project challenge failure")
        return self.payload  # type: ignore[return-value]


def _sample_inputs():
    resume_profile = parse_resume(SAMPLE_RESUME)
    job_analysis = analyze_jd(SAMPLE_JD)
    return resume_profile, job_analysis


def _valid_llm_payload() -> dict[str, Any]:
    return {
        "basic_questions": [
            {
                "question": "JobAgent 这个项目解决的核心问题是什么？",
                "evaluates": "是否能讲清项目背景与真实需求。",
                "answer_framework": "按问题背景、目标用户、解决方案三段式回答。",
            }
        ],
        "technical_deep_dive_questions": [
            {
                "question": "你在 JobAgent 里如何组织 FastAPI、Pydantic 和 workflow 之间的数据流？",
                "evaluates": "是否理解项目中的结构化数据边界。",
                "answer_framework": "从输入 schema、服务编排、Agent 输出和存储复盘来回答。",
            }
        ],
        "architecture_questions": [
            {
                "question": "如果 JobAgent 的分析步骤继续增加，你会怎么保持 workflow 可维护？",
                "evaluates": "是否具备架构演进和边界控制意识。",
                "answer_framework": "先讲现有分层，再讲状态管理、trace 和测试策略。",
            }
        ],
        "tradeoff_questions": [
            {
                "question": "为什么当前先保留 mock fallback，而不是强依赖 LLM？",
                "evaluates": "是否理解稳定性与产品体验之间的取舍。",
                "answer_framework": "从可用性、测试、成本和失败恢复角度回答。",
            }
        ],
        "interviewer_concerns": ["项目是否只是 demo，缺少真实输入输出约束。"],
        "improvement_suggestions": ["准备一组真实样例，展示分析输入、输出和 trace。"],
    }


def test_generate_project_challenges_mock_mode_returns_result() -> None:
    resume_profile, job_analysis = _sample_inputs()

    result = generate_project_challenges(resume_profile, job_analysis)

    assert isinstance(result, ProjectChallengeReport)
    assert result.basic_questions
    assert result.interviewer_concerns


def test_run_project_challenge_agent_defaults_to_mock_mode() -> None:
    resume_profile, job_analysis = _sample_inputs()

    result = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        use_llm=False,
    )

    assert result.metadata.mode == "mock"
    assert result.metadata.fallback_reason is None
    assert result.output.technical_deep_dive_questions


def test_run_project_challenge_agent_uses_llm_for_valid_payload() -> None:
    resume_profile, job_analysis = _sample_inputs()
    service = FakeLLMService(_valid_llm_payload())

    result = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "llm"
    assert result.metadata.fallback_reason is None
    assert result.output.basic_questions[0].question.startswith("JobAgent")


def test_generate_project_challenge_with_llm_validates_structured_output() -> None:
    resume_profile, job_analysis = _sample_inputs()
    service = FakeLLMService(_valid_llm_payload())

    result = generate_project_challenge_with_llm(
        resume_profile,
        job_analysis,
        service=service,  # type: ignore[arg-type]
    )

    assert result.tradeoff_questions
    assert result.architecture_questions[0].answer_framework


def test_run_project_challenge_agent_falls_back_when_llm_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("JOBAGENT_LLM_API_KEY", raising=False)
    resume_profile, job_analysis = _sample_inputs()

    result = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        use_llm=True,
    )

    assert result.metadata.mode == "fallback"
    assert result.metadata.fallback_reason == "LLMServiceError"
    assert result.output.basic_questions


def test_run_project_challenge_agent_falls_back_when_llm_raises() -> None:
    resume_profile, job_analysis = _sample_inputs()
    service = FakeLLMService(should_fail=True)

    result = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "fallback"
    assert result.metadata.fallback_reason == "LLMServiceError"
    assert result.output.tradeoff_questions


def test_run_project_challenge_agent_falls_back_when_llm_schema_invalid() -> None:
    resume_profile, job_analysis = _sample_inputs()
    service = FakeLLMService(
        {
            "basic_questions": [
                {
                    "question": "这个字段缺少 evaluates 和 answer_framework",
                }
            ]
        }
    )

    result = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "fallback"
    assert result.metadata.fallback_reason == "ValidationError"
    assert result.output.basic_questions
