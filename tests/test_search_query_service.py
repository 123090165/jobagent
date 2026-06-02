from __future__ import annotations

import pytest

from app.services.errors import JobAgentError
from app.services.search_query_service import generate_search_queries_from_resume


def test_generate_search_queries_includes_python_backend_role() -> None:
    queries = generate_search_queries_from_resume(
        "Built Python FastAPI services with SQL data access.",
        max_queries=5,
    )

    assert "Python Backend Engineer Shenzhen" in queries


def test_generate_search_queries_includes_ai_agent_role() -> None:
    queries = generate_search_queries_from_resume(
        "Worked on LLM agent workflows with LangGraph orchestration.",
        max_queries=5,
    )

    assert "AI Agent Developer Shenzhen" in queries


def test_generate_search_queries_includes_data_analyst_role() -> None:
    queries = generate_search_queries_from_resume(
        "Built SQL dashboard reporting for business data teams.",
        max_queries=5,
    )

    assert "Data Analyst Shenzhen" in queries


def test_generate_search_queries_includes_embedded_role() -> None:
    queries = generate_search_queries_from_resume(
        "Developed STM32 firmware and FPGA interfaces for embedded systems.",
        max_queries=5,
    )

    assert "Embedded Software Engineer Shenzhen" in queries


def test_generate_search_queries_dedupes_results() -> None:
    queries = generate_search_queries_from_resume(
        "Python Python FastAPI SQL SQL backend APIs.",
        max_queries=10,
    )

    assert queries.count("Python Backend Engineer Shenzhen") == 1


def test_generate_search_queries_respects_max_queries() -> None:
    queries = generate_search_queries_from_resume(
        "Python FastAPI SQL LLM Agent LangGraph Streamlit API Data Dashboard STM32 FPGA",
        max_queries=3,
    )

    assert len(queries) == 3


def test_generate_search_queries_rejects_empty_resume() -> None:
    with pytest.raises(JobAgentError) as exc_info:
        generate_search_queries_from_resume("   ")

    assert exc_info.value.error_code == "search_query_resume_empty"


@pytest.mark.parametrize("max_queries", [0, 11])
def test_generate_search_queries_rejects_invalid_max_queries(max_queries: int) -> None:
    with pytest.raises(JobAgentError) as exc_info:
        generate_search_queries_from_resume("Python FastAPI", max_queries=max_queries)

    assert exc_info.value.error_code == "search_query_limit_invalid"


def test_generate_search_queries_returns_fallback_queries_when_no_keyword_matches() -> None:
    queries = generate_search_queries_from_resume(
        "Student club leadership and communication projects.",
        max_queries=5,
    )

    assert queries == [
        "Software Engineer Shenzhen",
        "Graduate Software Engineer Hong Kong",
    ]
