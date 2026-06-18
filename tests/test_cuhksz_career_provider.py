from __future__ import annotations

from pathlib import Path

from app.application.job_search_usecases import create_job_search_run, execute_job_search_run
from app.schemas.job_search import JobSearchRunCreateRequest
from app.services.job_search_providers.cuhksz_career_provider import (
    CUHKSZ_CAREER_SEARCH_URL,
    NO_PROVIDER_MATCH_WARNING,
    CUHKSZCareerProvider,
)
from tests.test_job_search_live_api import FakeJSONLLM, _create_session_with_confirmed_profile

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROVIDER_SOURCE = Path("app/services/job_search_providers/cuhksz_career_provider.py")


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_cuhksz_list_page_fixture_parsing_extracts_expected_fields() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
            "https://career.cuhk.edu.cn/job/view/id/468294": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )

    results = provider.search_jobs(query="AI", location=None, limit=5)

    assert len(results) == 2
    first = results[0]
    assert first.title
    assert first.company
    assert first.location
    assert first.source_provider == "cuhksz_career"
    assert first.source_url == "https://career.cuhk.edu.cn/job/view/id/468293"
    assert "Published 2026-05-30" in first.snippet or "Published Date" in (first.raw_description or "")


def test_cuhksz_provider_keeps_candidates_without_provider_side_match() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )

    candidate = provider.search_jobs(query="speech recognition", location="Boston", limit=1)[0]

    assert candidate.source_url == "https://career.cuhk.edu.cn/job/view/id/468293"
    assert NO_PROVIDER_MATCH_WARNING in candidate.provider_warnings


def test_cuhksz_detail_page_parsing_extracts_description() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )

    candidate = provider.search_jobs(query="AI", location=None, limit=1)[0]

    assert candidate.raw_description is not None
    assert "Job Description:" in candidate.raw_description


def test_cuhksz_detail_fetch_failure_keeps_candidate_with_warning() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={},
        fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("boom")) if url != CUHKSZ_CAREER_SEARCH_URL else read_fixture("cuhksz_job_list_sample.html"),
    )

    candidate = provider.search_jobs(query="AI", location=None, limit=1)[0]

    assert candidate.raw_description is None
    assert candidate.provider_warnings
    assert candidate.source_url == "https://career.cuhk.edu.cn/job/view/id/468293"


def test_cuhksz_provider_source_does_not_contain_regressed_mojibake_labels() -> None:
    source = PROVIDER_SOURCE.read_text(encoding="utf-8")

    assert "閸忣剙寰冮崥宥囆" not in source
    assert "瀹搞儰缍旈崷鎵仯" not in source
    assert "閽栴亣绁" not in source
    assert 'COMPANY_LABELS = ["鍏徃鍚嶇О", "浼佷笟鍚嶇О"]' in source


def test_live_search_use_case_works_with_fake_cuhksz_provider(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-cuhksz-provider.sqlite3")
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
            "https://career.cuhk.edu.cn/job/view/id/468294": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=confirmed["profile_session"]["session_id"],
            search_mode="live_search",
            search_provider="cuhksz_career",
            use_llm=True,
            max_results=5,
        ),
        job_search_provider=provider,
        llm_service=FakeJSONLLM(),
    )

    completed = execute_job_search_run(
        run_response.job_search_run.job_search_run_id,
        job_search_provider=provider,
        llm_service=FakeJSONLLM(),
        max_results=5,
    )

    assert completed.job_search_run.status == "completed"
    assert completed.job_search_run.search_provider == "cuhksz_career"
    assert "cuhksz_career" in completed.steps[1].summary
