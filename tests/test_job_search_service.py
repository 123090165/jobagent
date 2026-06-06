from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.cuhksz_career import CUHKSZJobDetail, CUHKSZJobListItem
from app.schemas.search import SearchResultItem, SearchResultSet
from app.services import job_search_service
from app.services.errors import JobAgentError
from app.services.job_search_service import search_jobs
from app.services.public_job_storage_service import save_public_job_post


def _build_local_detail() -> CUHKSZJobDetail:
    jd_text = (
        "Responsibilities:\n"
        "- Build Python and FastAPI services.\n"
        "Requirements:\n"
        "- Strong SQL and testing fundamentals.\n"
        "Skills: Python, FastAPI, SQL"
    )
    return CUHKSZJobDetail(
        list_item=CUHKSZJobListItem(
            external_id="468293",
            title="AI Platform Intern",
            company="Example Tech",
            location="Shenzhen",
            job_type="Intern",
            education="Bachelor",
            published_at="2026-05-30",
            deadline="2026-07-01",
            detail_url="https://career.cuhk.edu.cn/job/view/id/468293",
        ),
        jd_text=jd_text,
        snippet=jd_text[:120],
        is_full_jd=True,
        confidence=0.88,
        warnings=[],
    )


def test_search_jobs_returns_search_result_set_from_mock_provider() -> None:
    result = search_jobs("python backend")

    assert isinstance(result, SearchResultSet)
    assert result.provider == "mock"
    assert result.query == "python backend"
    assert result.items
    assert result.items[0].source == "mock"
    assert result.items[0].skills
    assert result.items[0].jd_text is not None
    assert result.items[0].is_full_jd is True
    assert result.items[0].confidence > 0
    assert result.warnings == []
    assert isinstance(result.metadata, dict)


def test_search_jobs_respects_limit() -> None:
    result = search_jobs("llm engineer", limit=2)

    assert len(result.items) == 2


def test_search_jobs_supports_local_db_provider(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "search.sqlite3"
    save_public_job_post(_build_local_detail(), database_path=database_path)
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))

    result = search_jobs("AI Platform", provider="local_db", limit=3)

    assert result.provider == "local_db"
    assert len(result.items) == 1
    assert result.items[0].source == "cuhksz_career"
    assert result.items[0].skills == ["Python", "FastAPI", "SQL"]
    assert result.warnings == []
    assert isinstance(result.metadata, dict)


def test_search_jobs_supports_cuhksz_live_provider(monkeypatch) -> None:
    fake_item = SearchResultItem(
        title="AI 平台实习生",
        company="深圳示例科技有限公司",
        location="深圳",
        url="https://career.cuhk.edu.cn/job/view/id/468293",
        snippet="岗位职责：使用 Python 和 FastAPI。",
        source="cuhksz_career",
        retrieved_at=datetime.now(timezone.utc),
        jd_text="岗位职责：使用 Python 和 FastAPI。",
        quality_label="partial_jd",
        confidence=0.55,
    )

    monkeypatch.setitem(
        job_search_service._PROVIDERS,
        "cuhksz_live",
        type(
            "FakeCUHKSZLiveProvider",
            (),
            {
                "name": "cuhksz_live",
                "search_jobs": lambda self, query, limit=5: SearchResultSet(
                    query=query,
                    provider="cuhksz_live",
                    items=[fake_item],
                    warnings=[],
                    metadata={
                        "list_items_found": 2,
                        "detail_candidates": 1,
                        "detail_success": 1,
                        "detail_failed": 0,
                        "returned_count": 1,
                    },
                ),
            },
        )(),
    )

    result = search_jobs("Python", provider="cuhksz_live", limit=1)

    assert result.provider == "cuhksz_live"
    assert len(result.items) == 1
    assert result.items[0].source == "cuhksz_career"
    assert result.metadata["returned_count"] == 1


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
