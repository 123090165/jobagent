from __future__ import annotations

import json
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
    assert "jobSearchPreviewRequestId" in store
    assert "requestId === this.jobSearchPreviewRequestId" in store
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


def test_confirmed_page_routes_to_search_setup_instead_of_creating_search_run() -> None:
    confirmed_page = _read("pages/ProfileConfirmedPage.vue")
    search_setup_page = _read("pages/SearchMissionPage.vue")
    progress = _read("components/StepProgress.vue")
    router = _read("router/index.ts")

    assert "Set Search Preferences" in confirmed_page
    assert 'name: "search-mission"' in confirmed_page
    assert 'path: "/profile/:sessionId/search-mission"' in router
    assert "createJobSearch(" not in confirmed_page
    assert 'title="Search Setup"' in search_setup_page
    assert "Continue to Sources" in search_setup_page
    assert "interpretSearchMission(sessionId.value, true)" in search_setup_page
    assert "Interpret Mission" not in search_setup_page
    assert 'label: "Profile"' in progress
    assert 'label: "Search Setup"' in progress
    assert 'label: "Results"' in progress


def test_job_search_result_page_can_return_to_preview() -> None:
    job_search_page = _read("pages/JobSearchPage.vue")
    search_preview = _read("pages/SearchPreviewPage.vue")
    preview_controls = _read("composables/useSearchPreviewControls.ts")
    store = _read("stores/profileSession.ts")
    types = _read("types/profileSession.ts")

    assert "Back to Search Preview" in job_search_page
    assert 'name: "search-preview"' in job_search_page
    assert "jobSearchPreviewControls" in store
    assert "saveJobSearchPreviewControls" in store
    assert "useSearchPreviewControls" in search_preview
    assert "restorePreviewControls" in search_preview
    assert "canReuseStoredPreview" in search_preview
    assert "expectedStoredPreviewProvider" in preview_controls
    assert "saveCurrentPreviewControls" in search_preview
    assert "Score Breakdown" in job_search_page
    assert "Evidence" in job_search_page
    assert "Trace Details" in job_search_page
    assert "Provider Key" in job_search_page
    assert "Selected Sources" in job_search_page
    assert "Result Sources" in job_search_page
    assert "runProviderLabel" in job_search_page
    assert "resultSourceSummary" in job_search_page
    assert "formatProviderName" in job_search_page
    assert "formatSourceName" in job_search_page
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
    assert "BOSS" in search_preview
    assert "selectedProviderSearchSources" in search_preview
    assert "isBossSourceSelected" in search_preview
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
    preview_controls = _read("composables/useSearchPreviewControls.ts")
    browser_session = _read("composables/useBrowserHelperSession.ts")
    helper_service = _read("services/browserHelper.ts")
    source_service = _read("services/jobSearchSources.ts")

    assert "Browser Helper" in search_preview
    assert "Check Helper" in search_preview
    assert "Check BOSS Login" in search_preview
    assert "Open BOSS Login" in search_preview
    assert "Start Job Search" in search_preview
    assert "useBrowserHelperSession" in search_preview
    assert "pingBrowserHelper" in browser_session
    assert "checkBossLoginStatus" in browser_session
    assert "startBossLoginAutoRefresh" in browser_session
    assert "stopBossLoginAutoRefresh" in browser_session
    assert "BOSS login verified by a live page probe" in browser_session
    assert "fetchBossCandidates" in search_preview
    assert "startBrowserHelperJobSearch" in search_preview
    assert "legacySelectedSearchSources" in preview_controls
    assert "normalizeProviderSearchSources" in preview_controls
    assert "formatSearchSources" in search_preview
    assert "ProviderSearchSource" in source_service
    assert "formatProviderName" in source_service
    assert "formatSourceName" in source_service
    assert "normalizeProviderSearchSources" in source_service
    assert "providerSourcesForRun(profileSessionStore.jobSearchPreview)" in search_preview
    assert "backendProviderSourceLabel" in search_preview
    assert "Backend Sources" in search_preview
    assert "BOSS Queries" in search_preview
    assert "profileSessionStore.jobSearchPreviewControls?.selectedProviderSearchSources" in preview_controls
    assert "createBrowserHelperJobSearch" in search_preview
    assert "preview?.selected_sources" in preview_controls
    assert "!profileSessionStore.isJobSearchPreviewLoading" in search_preview
    assert "__jobagentHelper" in helper_service
    assert 'action: "searchBoss"' in helper_service
    assert "BossSearchDiagnostics" in helper_service
    assert "attemptedQueries" in helper_service
    assert "searchAttempts" in helper_service
    assert "cookieLoggedIn" in helper_service
    assert "sessionVerified" in helper_service


def test_browser_helper_boss_automation_is_available() -> None:
    helper_background = Path("browser-helper/background.js").read_text(encoding="utf-8")
    manifest = json.loads(Path("browser-helper/manifest.json").read_text(encoding="utf-8"))

    assert "BOSS_AUTOMATION_DISABLED_MESSAGE" not in helper_background
    assert "BOSS login is required before searching." in helper_background
    assert '"checkBossLogin"' in helper_background
    assert '"searchBoss"' in helper_background
    assert "BOSS current-page capture used DOM text only" in helper_background
    assert "isBossJobDetailUrl" in helper_background
    assert "capture_safety" in helper_background
    assert "cookies" in manifest["permissions"]
    assert "*://*.zhipin.com/*" in manifest.get("host_permissions", [])
    assert "*://zhipin.com/*" in manifest.get("host_permissions", [])
