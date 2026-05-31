from __future__ import annotations

import importlib.util
from dataclasses import dataclass

import pytest

from app.services.llm_service import LLMServiceError
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from app.workflows.langgraph_job_analysis_workflow import (
    LangGraphJobAnalysisWorkflowResult,
    run_langgraph_job_analysis_workflow,
)
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME

LANGGRAPH_INSTALLED = importlib.util.find_spec("langgraph") is not None


@dataclass
class _FakeCompiledGraph:
    builder: "_FakeStateGraph"

    def invoke(self, initial_state: dict):
        state = dict(initial_state)
        current = self.builder.entry_point
        while current:
            updates = self.builder.nodes[current](state) or {}
            state.update(updates)
            if current == self.builder.finish_point:
                break
            if current in self.builder.conditional_edges:
                next_step = self.builder.conditional_edges[current](state)
                current = next_step
            else:
                current = self.builder.edges.get(current)
        return state


class _FakeStateGraph:
    def __init__(self, state_type):
        self.state_type = state_type
        self.nodes = {}
        self.edges = {}
        self.conditional_edges = {}
        self.entry_point = None
        self.finish_point = None

    def add_node(self, name, func):
        self.nodes[name] = func

    def set_entry_point(self, name):
        self.entry_point = name

    def add_edge(self, source, target):
        self.edges[source] = target

    def add_conditional_edges(self, source, func):
        self.conditional_edges[source] = func

    def set_finish_point(self, name):
        self.finish_point = name

    def compile(self):
        return _FakeCompiledGraph(self)


class FailingLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        raise LLMServiceError("fake langgraph workflow failure")


class JDLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "job_title": "AI 应用开发工程师",
            "company": None,
            "location": None,
            "responsibilities": ["负责 Python 后端开发"],
            "required_skills": ["Python", "FastAPI", "SQL"],
            "preferred_skills": ["LangGraph"],
            "experience_requirements": ["有项目经验"],
            "education_requirements": [],
            "soft_skills": ["沟通"],
            "implicit_requirements": ["能把项目讲清楚"],
            "keywords": ["Python", "FastAPI", "SQL", "LangGraph"],
            "job_category": "AI / LLM 应用开发",
        }


class ResumeOptimizeLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "overall_issues": ["需要更明确对齐 JD 的 API 能力。"],
            "keywords_to_add": ["REST API"],
            "skills_section_suggestions": ["把 FastAPI 和 REST API 放在技能栏前半部分。"],
            "project_rewrite_suggestions": [
                {
                    "original": "JobAgent 求职分析工具",
                    "suggestion": "强调已有 API、schema 和测试职责，不新增事实。",
                    "reason": "只改写原有项目表达。",
                }
            ],
            "jd_targeted_bullets": ["补充 API 设计和测试覆盖说明。"],
            "do_not_exaggerate": ["不要新增没有真实使用过的技术栈。"],
            "missing_info_needed": ["如有真实数据，可补充接口数量或测试数量。"],
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
                    "evaluates": "是否理解数据流。",
                    "answer_framework": "从 schema、service、agent、storage 角度说明。",
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
                    "question": "为什么现在仍保留 mock fallback？",
                    "evaluates": "是否理解稳定性和可用性的取舍。",
                    "answer_framework": "从可用性、成本和失败恢复说明。",
                }
            ],
            "interviewer_concerns": ["项目是否缺少真实输入输出约束。"],
            "improvement_suggestions": ["准备真实样例输入输出和 trace 展示。"],
        }


def test_langgraph_workflow_requires_dependency_when_missing() -> None:
    if LANGGRAPH_INSTALLED:
        pytest.skip("langgraph is installed in this environment")

    with pytest.raises(RuntimeError, match="LangGraph is not installed"):
        run_langgraph_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)


def test_langgraph_workflow_can_run_with_fake_state_graph(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.workflows.langgraph_job_analysis_workflow._load_state_graph",
        lambda: _FakeStateGraph,
    )

    result = run_langgraph_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    assert isinstance(result, LangGraphJobAnalysisWorkflowResult)
    assert result.state.route_decision == "resume_optimize"
    assert result.state.missing_info_report is not None
    assert result.state.missing_info_report.summary
    assert "MissingInfoAgent" in [step.name for step in result.state.steps]


def test_langgraph_low_match_path_keeps_missing_info_report_with_fake_state_graph(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.workflows.langgraph_job_analysis_workflow._load_state_graph",
        lambda: _FakeStateGraph,
    )
    low_match_resume = """
    李四
    个人介绍：做过课程作业和文档整理，暂时没有后端项目经验。
    """
    demanding_jd = """
    高级 AI 平台工程师
    要求：熟悉 Python、FastAPI、SQL、Redis、Docker、LangGraph、RAG、LLM、OpenAI、Git。
    """

    result = run_langgraph_job_analysis_workflow(low_match_resume, demanding_jd)

    assert result.state.route_decision == "low_match_prepare"
    assert result.state.missing_info_report is not None
    assert result.state.missing_info_report.questions
    assert "MissingInfoAgent" in [step.name for step in result.state.steps]


def test_default_python_workflow_is_not_extended_with_missing_info_state() -> None:
    result = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    assert not hasattr(result.state, "missing_info_report")


@pytest.mark.skipif(not LANGGRAPH_INSTALLED, reason="langgraph is not installed")
def test_langgraph_workflow_standard_path_returns_compatible_result() -> None:
    result = run_langgraph_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)
    baseline = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    assert isinstance(result, LangGraphJobAnalysisWorkflowResult)
    assert result.final_report.markdown_report
    assert result.state.route_decision == "resume_optimize"
    assert set(result.final_report.model_dump()) == set(baseline.final_report.model_dump())

    step_names = [step.name for step in result.state.steps]
    assert step_names == [
        "ResumeParseAgent",
        "JDAnalysisAgent",
        "MatchAgent",
        "MissingInfoAgent",
        "MatchScoreRouter",
        "ResumeOptimizeAgent",
        "ProjectInterviewAgent",
        "ReportAgent",
    ]
    assert result.state.missing_info_report is not None


@pytest.mark.skipif(not LANGGRAPH_INSTALLED, reason="langgraph is not installed")
def test_langgraph_workflow_default_modes_are_mock() -> None:
    result = run_langgraph_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    assert all(step.status == "completed" for step in result.state.steps)
    assert {step.mode for step in result.state.steps} == {"mock"}
    assert all(step.guardrails for step in result.state.steps)
    assert all(step.workflow_run_id == result.state.workflow_run_id for step in result.state.steps)
    assert result.state.missing_info_report is not None


@pytest.mark.skipif(not LANGGRAPH_INSTALLED, reason="langgraph is not installed")
def test_langgraph_workflow_can_record_llm_modes() -> None:
    result = run_langgraph_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_jd=True,
        jd_llm_service=JDLLMService(),  # type: ignore[arg-type]
        use_llm_resume_optimize=True,
        resume_optimize_llm_service=ResumeOptimizeLLMService(),  # type: ignore[arg-type]
        use_llm_project_challenge=True,
        project_challenge_llm_service=ProjectChallengeLLMService(),  # type: ignore[arg-type]
    )

    step_by_name = {step.name: step for step in result.state.steps}
    assert step_by_name["JDAnalysisAgent"].mode == "llm"
    assert step_by_name["MissingInfoAgent"].mode == "mock"
    assert step_by_name["ResumeOptimizeAgent"].mode == "llm"
    assert step_by_name["ProjectInterviewAgent"].mode == "llm"
    assert result.final_report.optimization_result.keywords_to_add == ["REST API"]


@pytest.mark.skipif(not LANGGRAPH_INSTALLED, reason="langgraph is not installed")
def test_langgraph_workflow_llm_failures_fallback_without_breaking_flow() -> None:
    result = run_langgraph_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_jd=True,
        jd_llm_service=FailingLLMService(),  # type: ignore[arg-type]
        use_llm_resume_optimize=True,
        resume_optimize_llm_service=FailingLLMService(),  # type: ignore[arg-type]
        use_llm_project_challenge=True,
        project_challenge_llm_service=FailingLLMService(),  # type: ignore[arg-type]
    )

    step_by_name = {step.name: step for step in result.state.steps}
    assert step_by_name["JDAnalysisAgent"].mode == "fallback"
    assert step_by_name["ResumeOptimizeAgent"].mode == "fallback"
    assert step_by_name["ProjectInterviewAgent"].mode == "fallback"
    assert step_by_name["JDAnalysisAgent"].fallback_reason == "LLMServiceError"
    assert step_by_name["ResumeOptimizeAgent"].fallback_reason == "LLMServiceError"
    assert step_by_name["ProjectInterviewAgent"].fallback_reason == "LLMServiceError"
    assert step_by_name["MissingInfoAgent"].mode == "mock"
    assert result.final_report.markdown_report


@pytest.mark.skipif(not LANGGRAPH_INSTALLED, reason="langgraph is not installed")
def test_langgraph_workflow_low_match_path_is_traceable_and_safe() -> None:
    low_match_resume = """
    李四
    个人介绍：做过课程作业和文档整理，暂时没有后端项目经验。
    """
    demanding_jd = """
    高级 AI 平台工程师
    要求：熟悉 Python、FastAPI、SQL、Redis、Docker、LangGraph、RAG、LLM、OpenAI、Git。
    """

    result = run_langgraph_job_analysis_workflow(low_match_resume, demanding_jd)

    step_names = [step.name for step in result.state.steps]
    assert result.state.route_decision == "low_match_prepare"
    assert result.final_report.markdown_report
    assert "ResumeOptimizeAgent" not in step_names
    assert "ProjectInterviewAgent" not in step_names
    assert "MissingInfoAgent" in step_names
    assert "LowMatchPreparation" in step_names

    route_step = next(step for step in result.state.steps if step.name == "MatchScoreRouter")
    prep_step = next(step for step in result.state.steps if step.name == "LowMatchPreparation")
    assert "below 50" in route_step.summary
    assert "low-match" in prep_step.summary
    assert result.state.missing_info_report is not None
    assert result.final_report.optimization_result is not None
    assert result.final_report.project_challenge_report is not None
