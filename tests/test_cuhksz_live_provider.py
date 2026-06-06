from __future__ import annotations

from pathlib import Path

import pytest

from app.services.live_job.fetcher import LiveJobFetchError
from app.services.live_job.provider import CUHKSZLiveProvider
from app.services.public_job_storage_service import list_public_job_posts

FIXTURES_DIR = Path(__file__).parent / "fixtures"
LIST_URL = "https://career.cuhk.edu.cn/job/search/d_category/102"
DETAIL_URL_1 = "https://career.cuhk.edu.cn/job/view/id/468293"
DETAIL_URL_2 = "https://career.cuhk.edu.cn/job/view/id/468294"


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_cuhksz_live_provider_returns_search_results(monkeypatch) -> None:
    list_html = read_fixture("cuhksz_job_list_sample.html")
    detail_html = read_fixture("cuhksz_job_detail_sample.html")

    def fake_fetch(url: str, timeout_seconds: int = 15) -> str:
        if url == LIST_URL:
            return list_html
        if url in {DETAIL_URL_1, DETAIL_URL_2}:
            return detail_html
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.live_job.provider.fetch_public_html", fake_fetch)
    monkeypatch.setattr("app.services.live_job.provider.time.sleep", lambda seconds: None)

    provider = CUHKSZLiveProvider(list_url=LIST_URL, detail_request_sleep_seconds=0)
    result = provider.search_jobs("AI 实习 深圳", limit=1)

    assert result.provider == "cuhksz_live"
    assert result.query == "AI 实习 深圳"
    assert len(result.items) == 1
    assert result.items[0].source == "cuhksz_career"
    assert result.items[0].title == "AI 平台实习生"
    assert result.items[0].jd_text
    assert result.items[0].quality_label == "full_jd"


def test_cuhksz_live_provider_raises_on_list_fetch_failure(monkeypatch) -> None:
    def fake_fetch(url: str, timeout_seconds: int = 15) -> str:
        raise LiveJobFetchError("boom")

    monkeypatch.setattr("app.services.live_job.provider.fetch_public_html", fake_fetch)

    provider = CUHKSZLiveProvider(list_url=LIST_URL, detail_request_sleep_seconds=0)

    with pytest.raises(LiveJobFetchError, match="boom"):
        provider.search_jobs("AI", limit=1)


def test_cuhksz_live_provider_skips_failed_detail_and_continues(monkeypatch) -> None:
    list_html = read_fixture("cuhksz_job_list_sample.html")
    detail_html = read_fixture("cuhksz_job_detail_sample.html")

    def fake_fetch(url: str, timeout_seconds: int = 15) -> str:
        if url == LIST_URL:
            return list_html
        if url == DETAIL_URL_1:
            raise RuntimeError("detail failed")
        if url == DETAIL_URL_2:
            return detail_html
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.live_job.provider.fetch_public_html", fake_fetch)
    monkeypatch.setattr("app.services.live_job.provider.time.sleep", lambda seconds: None)

    provider = CUHKSZLiveProvider(list_url=LIST_URL, detail_request_sleep_seconds=0)
    result = provider.search_jobs("深圳", limit=2)

    assert len(result.items) == 1
    assert result.items[0].title == "数据工程师"


def test_cuhksz_live_provider_can_save_to_local_db_without_duplicates(tmp_path, monkeypatch) -> None:
    list_html = read_fixture("cuhksz_job_list_sample.html")
    detail_html = read_fixture("cuhksz_job_detail_sample.html")
    database_path = tmp_path / "live-provider.sqlite3"

    def fake_fetch(url: str, timeout_seconds: int = 15) -> str:
        if url == LIST_URL:
            return list_html
        if url in {DETAIL_URL_1, DETAIL_URL_2}:
            return detail_html
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.live_job.provider.fetch_public_html", fake_fetch)
    monkeypatch.setattr("app.services.live_job.provider.time.sleep", lambda seconds: None)

    provider = CUHKSZLiveProvider(
        list_url=LIST_URL,
        save_to_local_db=True,
        database_path=database_path,
        detail_request_sleep_seconds=0,
    )

    first_result = provider.search_jobs("AI", limit=1)
    second_result = provider.search_jobs("AI", limit=1)
    stored_jobs = list_public_job_posts(database_path=database_path)

    assert len(first_result.items) == 1
    assert len(second_result.items) == 1
    assert len(stored_jobs) == 1
    assert stored_jobs[0]["external_id"] == "468293"
