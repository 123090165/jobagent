from __future__ import annotations

import pytest

from app.services.mock_pipeline import run_mock_pipeline


SAMPLE_RESUME = """
张三
技能：Python、FastAPI、Pydantic、Streamlit、SQL、Git
项目：JobAgent 求职分析工具，使用 Streamlit 和 Pydantic 生成结构化匹配报告。
负责：设计 mock pipeline，并生成 Markdown 报告。
"""

SAMPLE_JD = """
AI 应用开发工程师
职责：负责 Python 后端开发，设计 REST API，参与 LLM 应用建设。
要求：熟悉 Python、FastAPI、SQL、Pydantic，有 Git 使用经验。
加分：了解 RAG、LangGraph、Docker。
"""


def test_run_mock_pipeline_returns_structured_report() -> None:
    result = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)

    assert result.resume_profile.skills
    assert result.job_analysis.required_skills
    assert result.match_report.overall_score > 0
    assert "匹配度总览" in result.markdown_report
    assert "项目拷打问题" in result.markdown_report


def test_run_mock_pipeline_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        run_mock_pipeline("", SAMPLE_JD)

    with pytest.raises(ValueError):
        run_mock_pipeline(SAMPLE_RESUME, "")
