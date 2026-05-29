from __future__ import annotations

from typing import Any

from app.agents.jd_analysis_agent import analyze_jd, analyze_jd_with_llm
from app.services.llm_service import LLMServiceError, parse_json_object


SAMPLE_JD = """
AI 应用开发工程师
职责：负责 Python 后端开发，设计 REST API，参与 LLM 应用建设。
要求：熟悉 Python、FastAPI、SQL、Pydantic，有 Git 使用经验。
加分：了解 RAG、LangGraph、Docker。
"""


class FakeLLMService:
    def __init__(self, payload: dict[str, Any] | None = None, should_fail: bool = False) -> None:
        self.payload = payload or {}
        self.should_fail = should_fail

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self.should_fail:
            raise LLMServiceError("fake failure")
        return self.payload


def test_analyze_jd_with_llm_validates_structured_output() -> None:
    service = FakeLLMService(
        {
            "job_title": "AI 应用开发工程师",
            "responsibilities": ["负责 Python 后端开发"],
            "required_skills": ["Python", "FastAPI", "SQL"],
            "preferred_skills": ["RAG", "LangGraph"],
            "keywords": ["Python", "FastAPI", "SQL", "RAG", "LangGraph"],
            "job_category": "AI / LLM 应用开发",
        }
    )

    result = analyze_jd_with_llm(SAMPLE_JD, service=service)  # type: ignore[arg-type]

    assert result.raw_jd == SAMPLE_JD
    assert result.job_title == "AI 应用开发工程师"
    assert "Python" in result.required_skills
    assert "RAG" in result.preferred_skills


def test_analyze_jd_falls_back_to_mock_when_llm_fails() -> None:
    service = FakeLLMService(should_fail=True)

    result = analyze_jd(SAMPLE_JD, use_llm=True, service=service)  # type: ignore[arg-type]

    assert result.raw_jd == SAMPLE_JD.strip()
    assert result.required_skills
    assert "Python" in result.keywords


def test_parse_json_object_accepts_markdown_fenced_json() -> None:
    payload = parse_json_object('```json\n{"job_title": "Backend Engineer"}\n```')

    assert payload == {"job_title": "Backend Engineer"}
