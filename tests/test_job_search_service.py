from __future__ import annotations

import pytest

from app.schemas.search import SearchResultSet
from app.services.errors import JobAgentError
from app.services.job_search_service import search_jobs


def test_search_jobs_returns_search_result_set_from_mock_provider() -> None:
    result = search_jobs("python backend")

    assert isinstance(result, SearchResultSet)
    assert result.provider == "mock"
    assert result.query == "python backend"
    assert result.items
    assert result.items[0].source == "mock"


def test_search_jobs_respects_limit() -> None:
    result = search_jobs("llm engineer", limit=2)

    assert len(result.items) == 2


def test_search_jobs_rejects_empty_query() -> None:
    with pytest.raises(JobAgentError, match="cannot be empty") as exc_info:
        search_jobs("   ")

    assert exc_info.value.error_code == "search_query_invalid"


def test_search_jobs_rejects_invalid_limit() -> None:
    with pytest.raises(JobAgentError, match="between 1 and 20") as exc_info:
        search_jobs("python", limit=0)

    assert exc_info.value.error_code == "search_limit_invalid"


def test_search_jobs_rejects_disabled_gemini_cli_provider() -> None:
    with pytest.raises(JobAgentError, match="disabled") as exc_info:
        search_jobs("python", provider="gemini_cli")

    assert exc_info.value.error_code == "search_provider_disabled"


def test_search_jobs_rejects_unknown_provider() -> None:
    with pytest.raises(JobAgentError, match="not supported") as exc_info:
        search_jobs("python", provider="unknown")

    assert exc_info.value.error_code == "search_provider_unsupported"
