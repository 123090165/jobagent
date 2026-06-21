from __future__ import annotations

from pathlib import Path

WEB_SRC = Path("web/src")


def _read(path: str) -> str:
    return (WEB_SRC / path).read_text(encoding="utf-8")


def test_search_preview_route_is_separate_from_job_search_results() -> None:
    router = _read("router/index.ts")

    assert 'name: "search-preview"' in router
    assert 'path: "/profile/:sessionId/search-preview"' in router
    assert 'name: "job-search"' in router
    assert 'path: "/jobs/:runId"' in router


def test_frontend_calls_backend_search_preview_endpoint() -> None:
    api = _read("api/profileSessions.ts")
    store = _read("stores/profileSession.ts")
    types = _read("types/profileSession.ts")

    assert "previewJobSearchRun" in api
    assert '"/api/v1/job-search-runs/preview"' in api
    assert "previewJobSearch(" in store
    assert "jobSearchPreview" in store
    assert "provider_search_terms" in types
    assert "provider_search_urls" in types


def test_confirmed_page_routes_to_preview_instead_of_creating_search_run() -> None:
    confirmed_page = _read("pages/ProfileConfirmedPage.vue")

    assert "Preview Job Search" in confirmed_page
    assert 'name: "search-preview"' in confirmed_page
    assert "createJobSearch(" not in confirmed_page


def test_job_search_result_page_can_return_to_preview() -> None:
    job_search_page = _read("pages/JobSearchPage.vue")

    assert "Back to Search Preview" in job_search_page
    assert 'name: "search-preview"' in job_search_page


def test_search_preview_page_shows_provider_specific_search_urls() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")

    assert "CUHKSZ Search Terms" in search_preview
    assert "CUHKSZ Search URLs" in search_preview
    assert "provider_search_terms" in search_preview
    assert "provider_search_urls" in search_preview
