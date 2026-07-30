"""回归验证frontend search preview flow的正常链路、失败边界和兼容契约。"""

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


def test_frontend_keeps_internal_search_planning_for_boss_only() -> None:
    api = _read("api/profileSessions.ts")
    store = _read("stores/profileSession.ts")
    types = _read("types/profileSession.ts")
    setup_page = _read("pages/SearchPreviewPage.vue")

    assert "previewJobSearchRun" in api
    assert '"/api/v1/job-search-runs/preview"' in api
    assert "previewJobSearch(" in store
    assert "jobSearchPreview: JobSearchPreview | null" not in store
    assert "jobSearchPreviewRequestId" not in store
    assert '\"Search planning\"' in setup_page
    assert "profileSessionStore.previewJobSearch(buildPayload())" in setup_page
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


def test_profile_routes_to_unified_search_setup_without_an_extra_mission_page() -> None:
    confirmed_page = _read("pages/ProfileConfirmedPage.vue")
    draft_page = _read("pages/ProfileDraftPage.vue")
    search_setup_page = _read("pages/SearchPreviewPage.vue")
    intent_form = _read("components/SearchIntentForm.vue")
    progress = _read("components/StepProgress.vue")
    router = _read("router/index.ts")

    assert "New Job Search" in confirmed_page
    assert 'name: "search-preview"' in confirmed_page
    assert 'name: "search-preview"' in draft_page
    assert 'path: "/profile/:sessionId/search-mission"' in router
    assert 'redirect: (to) =>' in router
    assert "createJobSearch(" not in confirmed_page
    assert 'title="New Job Search"' in search_setup_page
    assert "<SearchIntentForm" in search_setup_page
    assert "prepareForSearch(" in search_setup_page
    assert "saveSearchMission(props.sessionId, input)" in intent_form
    assert "interpretSearchMission(" in intent_form
    assert "confirmSearchMission(props.sessionId)" in intent_form
    assert "What are you looking for?" in intent_form
    assert "More preferences" in intent_form
    assert "Search plan and diagnostics" not in search_setup_page
    assert "Refresh Preview" not in search_setup_page
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
    assert "canReuseStoredPreview" not in search_preview
    assert "expectedStoredPreviewProvider" not in preview_controls
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


def test_search_setup_page_keeps_only_user_facing_controls() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")

    assert "Provider Search Terms" not in search_preview
    assert "Provider Search URLs" not in search_preview
    assert "Query Budget" not in search_preview
    assert "Search Intent" not in search_preview
    assert "Recall And Ranking Plan" not in search_preview
    assert "Recruiting Websites" in search_preview
    assert "CUHKSZ Career" in search_preview
    assert "LinkedIn" in search_preview
    assert "RemoteOK" in search_preview
    assert "BOSS" in search_preview
    assert "selectedProviderSearchSources" in search_preview
    assert "isBossSourceSelected" in search_preview
    assert "selected_sources" in search_preview


def test_search_parameters_do_not_trigger_automatic_preview_requests() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")
    intent_form = _read("components/SearchIntentForm.vue")

    assert "watch(" not in search_preview
    assert "refreshPreview" not in search_preview
    assert "loadJobSearchProviderStatus" not in search_preview
    assert "loadLlmStatus" not in search_preview
    assert "prepareForSearch(" in search_preview
    assert (
        search_preview.index("prepareForSearch(")
        < search_preview.index("createJobSearch(buildPayload())")
    )
    assert "saveSearchMission(props.sessionId, input)" in intent_form


def test_search_preview_page_exposes_browser_helper_probe() -> None:
    search_preview = _read("pages/SearchPreviewPage.vue")
    preview_controls = _read("composables/useSearchPreviewControls.ts")
    browser_session = _read("composables/useBrowserHelperSession.ts")
    helper_service = _read("services/browserHelper.ts")
    source_service = _read("services/jobSearchSources.ts")

    assert "Browser Helper and BOSS login will be checked after Start." in search_preview
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
    assert "ProviderSearchSource" in source_service
    assert "formatProviderName" in source_service
    assert "formatSourceName" in source_service
    assert "normalizeProviderSearchSources" in source_service
    assert "createBrowserHelperJobSearch" in search_preview
    assert "providerSearchSources.value" in search_preview
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
