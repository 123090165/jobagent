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
    assert "selected_sources" in types
    assert "recall_queries" in types
    assert "ranking_signals" in types
    assert "search_source_kind" in types
    assert "createBrowserHelperJobSearchRun" in api
    assert '"/api/v1/job-search-runs/browser-helper"' in api
    assert "createBrowserHelperJobSearch(" in store
    assert "CreateBrowserHelperJobSearchPayload" in types


def test_confirmed_page_routes_to_preview_instead_of_creating_search_run() -> None:
    confirmed_page = _read("pages/ProfileConfirmedPage.vue")

    assert "Preview Job Search" in confirmed_page
    assert 'name: "search-preview"' in confirmed_page
    assert "createJobSearch(" not in confirmed_page


def test_job_search_result_page_can_return_to_preview() -> None:
    job_search_page = _read("pages/JobSearchPage.vue")
    types = _read("types/profileSession.ts")

    assert "Back to Search Preview" in job_search_page
    assert 'name: "search-preview"' in job_search_page
    assert "Score Breakdown" in job_search_page
    assert "Evidence" in job_search_page
    assert "Trace Details" in job_search_page
    assert "score_breakdown" in types
    assert "evidence_quotes" in types


def test_search_preview_page_shows_provider_specific_search_urls() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")

    assert "Provider Search Terms" in search_preview
    assert "Provider Search URLs" in search_preview
    assert "provider_search_terms" in search_preview
    assert "provider_search_urls" in search_preview
    assert "Recruiting Websites" in search_preview
    assert "CUHKSZ Career" in search_preview
    assert "LinkedIn" in search_preview
    assert "RemoteOK" in search_preview
    assert "selected_sources" in search_preview


def test_search_preview_page_shows_query_budget() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")
    types = _read("types/profileSession.ts")

    assert "Query Budget" in search_preview
    assert "estimated_provider_requests" in search_preview
    assert "estimated_total_llm_requests" in search_preview
    assert "query_strategy_notes" in search_preview
    assert "estimated_llm_filtering_requests" in types


def test_search_preview_page_shows_generalized_search_intent() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")
    types = _read("types/profileSession.ts")

    assert "Search Intent" in search_preview
    assert "Role Families" in search_preview
    assert "Industry Domains" in search_preview
    assert "Evidence Skills" in search_preview
    assert "Generic Tools" in search_preview
    assert "search_intent" in types
    assert "interface JobSearchIntent" in types


def test_search_preview_page_separates_recall_queries_from_ranking_signals() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")

    assert "Recall And Ranking Plan" in search_preview
    assert "Recall Queries" in search_preview
    assert "Ranking Signals" in search_preview


def test_search_preview_page_exposes_browser_helper_probe() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")
    helper_service = _read("services/browserHelper.ts")

    assert "Browser Helper" in search_preview
    assert "Check Helper" in search_preview
    assert "Import Demo Candidate" in search_preview
    assert "pingBrowserHelper" in search_preview
    assert "fetchBrowserHelperDemoCandidates" in search_preview
    assert "__jobagentHelper" in helper_service
    assert "searchDemo" in helper_service
