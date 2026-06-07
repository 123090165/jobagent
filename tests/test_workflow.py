from __future__ import annotations

import pytest

from app.agents.match_agent import run_match_agent
from app.schemas.job import JobAnalysis
from app.schemas.resume import ProjectExperience, ResumeProfile
from app.services.llm_service import LLMServiceError
from app.services.mock_pipeline import run_mock_pipeline
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


class FailingLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        raise LLMServiceError("fake workflow failure")


class ResumeOptimizeLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "overall_issues": ["需要更明确地对齐 JD 的 API 能力。"],
            "keywords_to_add": ["REST API"],
            "skills_section_suggestions": ["把 FastAPI 和 REST API 放在技能栏前半部分。"],
            "project_rewrite_suggestions": [
                {
                    "original": "JobAgent 求职分析工具",
                    "suggestion": "基于已有 JobAgent 项目强调 API、schema 和测试职责。",
                    "reason": "只改写已有项目表达，不新增事实。",
                }
            ],
            "jd_targeted_bullets": ["基于已有项目补充 API 设计和测试覆盖说明。"],
            "do_not_exaggerate": ["不要新增没有真实使用过的技术栈。"],
            "missing_info_needed": ["如有真实数据，可补充测试数量或接口数量。"],
        }


class ProjectChallengeLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "basic_questions": [
                {
                    "question": "JobAgent 解决的核心问题是什么？",
                    "evaluates": "是否能讲清项目背景。",
                    "answer_framework": "按问题、目标用户、方案来回答。",
                }
            ],
            "technical_deep_dive_questions": [
                {
                    "question": "你在 JobAgent 里如何组织 FastAPI、Pydantic 和 workflow？",
                    "evaluates": "是否理解项目中的数据流。",
                    "answer_framework": "从 schema、service、agent、storage 角度回答。",
                }
            ],
            "architecture_questions": [
                {
                    "question": "如果分析步骤继续增加，你会怎么保持 workflow 可维护？",
                    "evaluates": "是否具备架构演进意识。",
                    "answer_framework": "从状态、trace 和测试三方面回答。",
                }
            ],
            "tradeoff_questions": [
                {
                    "question": "为什么现在保留 mock fallback？",
                    "evaluates": "是否理解稳定性和可用性的取舍。",
                    "answer_framework": "从可用性、成本和失败恢复说明。",
                }
            ],
            "interviewer_concerns": ["项目是否缺少真实输入输出约束。"],
            "improvement_suggestions": ["准备真实样例演示结构化输入和 trace。"],
        }


def test_job_analysis_workflow_records_step_trace() -> None:
    result = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    assert result.final_report.markdown_report
    assert result.state.resume_profile is not None
    assert result.state.job_analysis is not None
    assert result.state.match_report is not None
    assert [step.name for step in result.state.steps] == [
        "ResumeParseAgent",
        "JDAnalysisAgent",
        "MatchAgent",
        "ResumeOptimizeAgent",
        "ProjectInterviewAgent",
        "ReportAgent",
    ]
    assert all(step.status == "completed" for step in result.state.steps)
    assert {step.mode for step in result.state.steps} == {"mock"}
    assert all(step.guardrails for step in result.state.steps)
    assert result.state.workflow_run_id
    assert all(step.workflow_run_id == result.state.workflow_run_id for step in result.state.steps)
    assert all(step.duration_ms >= 0 for step in result.state.steps)
    assert result.final_report.match_report.requirement_matches


def test_match_agent_builds_requirement_matches_with_evidence() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI SQLite backend project",
        skills=["Python", "FastAPI"],
        projects=[
            ProjectExperience(
                name="Tracker API",
                description="Built backend APIs with FastAPI and SQLite.",
                technologies=["FastAPI", "SQLite"],
                highlights=["Designed REST endpoints for application tracking."],
                raw_text="Built backend APIs with FastAPI and SQLite.",
            )
        ],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need FastAPI and SQL experience.",
        required_skills=["FastAPI", "SQL"],
        responsibilities=["Build backend APIs"],
        keywords=["FastAPI", "SQL"],
    )

    report = run_match_agent(resume_profile, job_analysis).output

    fastapi_match = next(item for item in report.requirement_matches if "FastAPI" in item.requirement)
    assert fastapi_match.match_level == "matched"
    assert fastapi_match.resume_evidence


def test_match_agent_marks_missing_requirement_with_gap_and_hint() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI backend project",
        skills=["Python", "FastAPI"],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need Kubernetes experience.",
        required_skills=["Kubernetes"],
        keywords=["Kubernetes"],
    )

    report = run_match_agent(resume_profile, job_analysis).output

    kubernetes_match = next(item for item in report.requirement_matches if "Kubernetes" in item.requirement)
    assert kubernetes_match.match_level == "missing"
    assert kubernetes_match.gap_reason
    assert kubernetes_match.improvement_hint


def test_mock_pipeline_delegates_to_workflow_without_changing_contract() -> None:
    pipeline_report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)
    workflow_report = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD).final_report

    assert pipeline_report.model_dump() == workflow_report.model_dump()


def test_job_analysis_workflow_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        run_job_analysis_workflow("", SAMPLE_JD)

    with pytest.raises(ValueError, match="jd_text cannot be empty"):
        run_job_analysis_workflow(SAMPLE_RESUME, "")


def test_job_analysis_workflow_records_llm_fallback_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_jd=True,
        jd_llm_service=FailingLLMService(),  # type: ignore[arg-type]
    )

    jd_step = next(step for step in result.state.steps if step.name == "JDAnalysisAgent")
    assert jd_step.mode == "fallback"
    assert jd_step.fallback_reason == "LLMServiceError"
    assert "回退 mock" in jd_step.summary
    assert result.final_report.job_analysis.required_skills


def test_job_analysis_workflow_records_resume_optimize_llm_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_resume_optimize=True,
        resume_optimize_llm_service=ResumeOptimizeLLMService(),  # type: ignore[arg-type]
    )

    optimize_step = next(step for step in result.state.steps if step.name == "ResumeOptimizeAgent")
    assert optimize_step.mode == "llm"
    assert optimize_step.fallback_reason is None
    assert "使用 LLM 简历优化" in optimize_step.summary
    assert result.final_report.optimization_result.keywords_to_add == ["REST API"]


def test_job_analysis_workflow_records_resume_optimize_fallback_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_resume_optimize=True,
        resume_optimize_llm_service=FailingLLMService(),  # type: ignore[arg-type]
    )

    optimize_step = next(step for step in result.state.steps if step.name == "ResumeOptimizeAgent")
    assert optimize_step.mode == "fallback"
    assert optimize_step.fallback_reason == "LLMServiceError"
    assert "简历优化失败，已回退 mock" in optimize_step.summary
    assert result.final_report.optimization_result.jd_targeted_bullets


def test_job_analysis_workflow_records_project_challenge_llm_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_project_challenge=True,
        project_challenge_llm_service=ProjectChallengeLLMService(),  # type: ignore[arg-type]
    )

    challenge_step = next(step for step in result.state.steps if step.name == "ProjectInterviewAgent")
    assert challenge_step.mode == "llm"
    assert challenge_step.fallback_reason is None
    assert "使用 LLM 项目追问" in challenge_step.summary
    assert result.final_report.project_challenge_report.basic_questions


def test_job_analysis_workflow_records_project_challenge_fallback_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_project_challenge=True,
        project_challenge_llm_service=FailingLLMService(),  # type: ignore[arg-type]
    )

    challenge_step = next(step for step in result.state.steps if step.name == "ProjectInterviewAgent")
    assert challenge_step.mode == "fallback"
    assert challenge_step.fallback_reason == "LLMServiceError"
    assert "项目追问失败，已回退 mock" in challenge_step.summary
    assert result.final_report.project_challenge_report.technical_deep_dive_questions
