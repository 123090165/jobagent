from __future__ import annotations

import json
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_browser_helper_manifest_exposes_current_page_capture_side_panel() -> None:
    manifest = json.loads(_read("browser-helper/manifest.json"))

    assert manifest["manifest_version"] == 3
    assert "sidePanel" in manifest["permissions"]
    assert "activeTab" in manifest["permissions"]
    assert "scripting" in manifest["permissions"]
    assert "storage" in manifest["permissions"]
    assert "cookies" in manifest["permissions"]
    assert manifest["side_panel"]["default_path"] == "sidepanel.html"
    assert "http://127.0.0.1:8000/*" in manifest["host_permissions"]
    assert "http://localhost:8000/*" in manifest["host_permissions"]
    assert "*://*.zhipin.com/*" in manifest.get("host_permissions", [])
    assert "*://zhipin.com/*" in manifest.get("host_permissions", [])
    assert "<all_urls>" not in manifest.get("host_permissions", [])


def test_browser_helper_background_supports_user_triggered_current_page_capture() -> None:
    background = _read("browser-helper/background.js")

    assert "analyzeCurrentJob" in background
    assert "chrome.tabs.query({ active: true, currentWindow: true })" in background
    assert "chrome.scripting.executeScript" in background
    assert "captureCurrentJobPage" in background
    assert "document.body?.innerText" in background
    assert "/api/v1/browser/job-captures`" in background
    assert "/analyze`" in background
    assert "analysis_mode: requestedAnalysisMode" in background
    assert "llm_provider: requestedLlmProvider" in background
    assert "CURRENT_PAGE_MIN_TEXT_LENGTH = 80" in background
    assert "Generic visible-text extractor was used" in background
    assert "chrome.sidePanel.setPanelBehavior" in background
    assert "function initializeSidePanelBehavior()" in background
    assert 'typeof update.catch === "function"' in background


def test_boss_search_and_current_page_capture_are_both_available() -> None:
    background = _read("browser-helper/background.js")

    assert "BOSS_AUTOMATION_DISABLED_MESSAGE" not in background
    assert '"checkBossLogin"' in background
    assert '"searchBoss"' in background
    assert "BOSS login is required before searching." in background
    assert "fetchBossJobsFromWorkerApi" in background
    assert "fetchBossJobsFromPageApi" in background
    assert "BOSS current-page capture used DOM text only" in background
    assert "isBossJobDetailUrl" in background
    assert "\\/job_detail\\/" in background
    assert "(?:\\.html)?" in background
    assert "capture_safety" in background
    assert "BOSS appears to require security verification" in background
    assert "searchBossJobs({ queries, location, jobType, limit })" in background


def test_current_page_capture_injected_function_is_self_contained() -> None:
    background = _read("browser-helper/background.js")
    function_body = background.split("function captureCurrentJobPage", 1)[1].split(
        "\nfunction inferCaptureSource",
        1,
    )[0]

    assert "compactVisibleText(" not in function_body
    assert "inferCaptureSource(" not in function_body
    assert "looksLikeJobPage(" not in function_body
    assert "uniqueCaptureWarnings(" not in function_body
    assert "CURRENT_PAGE_CAPTURE_VERSION" not in function_body
    assert "CURRENT_PAGE_PREVIEW_LENGTH" not in function_body
    assert "captureVersion" in function_body
    assert "previewLength" in function_body


def test_browser_helper_side_panel_exposes_required_states_and_settings() -> None:
    html = _read("browser-helper/sidepanel.html")
    script = _read("browser-helper/sidepanel.js")
    background = _read("browser-helper/background.js")

    assert "Conversation" in html
    assert "Analysis profile" in html
    assert "Profile session" not in html
    assert "Capture current JD" in html
    assert "without running match analysis" in html
    assert "Optional match analysis" in html
    assert "Analyze JD match" in html
    assert "JD analysis" in html
    assert "Ask about this JD" in html
    assert "Send question" in html
    assert "The captured JD is attached to the selected conversation" in html
    assert "Keep analyzed JD in this conversation" not in html
    assert "Compare with saved job" in html
    assert "chrome.storage.local" in script
    assert "chrome.runtime.sendMessage" in script
    assert 'analysisMode: nodes.useLlm.checked ? "llm" : "deterministic"' in script
    assert 'llmProvider: "deepseek"' in script
    assert "saved.useLlm !== false" in script
    assert "chrome.permissions.request" in script
    assert "chrome.permissions.remove" in script
    assert "https://www.zhipin.com/*" in script
    assert "Reading the current BOSS job page" in script
    assert 'action: "captureCurrentJob"' in script
    assert 'action: "analyzeCapturedJob"' in script
    assert 'type: "browser_capture"' in script
    assert 'action: "sendAssistantTurn"' in script
    assert 'action: "attachAssistantBrowserCapture"' in script
    assert "capture.jd_text" in script
    assert "attachCaptureToConversation" in script
    assert "capture: { ...capture, ...(payload.capture || {}) }" in background
    assert "notifyAssistantContextUpdated" in background
    assert "JOBAGENT_HELPER_CONTEXT_UPDATED" in _read("browser-helper/bridge.js")
    assert 'type: "saved_job"' in script
    assert "renderAnalysisReport" in script
    assert "configureAnalysisProfiles" in script
    assert "profiles.length === 1" in script
    assert "(Default)" in script
    assert 'nodes.chatStage.classList.remove("hidden")' in script
    assert 'nodes.analysisControls.classList.remove("hidden")' in script
    assert 'requestPair: true' in script
    assert "chrome.storage.onChanged.addListener" in script
    assert "refreshAssistantState" in script
    assert "void init().catch(renderInitializationFailure)" in script
    assert "function renderInitializationFailure(error)" in script
    assert "function bindAsyncEvent(node, eventName, handler)" in script
    assert ".catch(renderActionFailure)" in script
    assert "function revokeTemporaryPermission(origin)" in script


def test_browser_helper_chat_token_is_session_only_and_sent_as_bearer() -> None:
    background = _read("browser-helper/background.js")

    assert "chrome.storage.session.set" in background
    assert "chrome.storage.session.get" in background
    assert '"Authorization": `Bearer ${session.accessToken}`' in background
    assert 'message.action === "bindJobAgentSession"' in background
    assert 'message.action === "getBrowserHelperConnectionStatus"' in background
    assert 'message.action === "getAssistantState"' in background
    assert "/api/v1/browser-helper/context-catalog" in background
    assert 'message.action === "sendAssistantTurn"' in background
    assert 'message.action === "pinAssistantSearchResult"' in background
    assert 'query.set("pair_browser_helper", "1")' in background
    assert "openOrFocusAssistantTab" in background
    assert "chrome.tabs.query({})" in background
    assert "chrome.tabs.update(existing.tab.id" in background
    assert "chrome.windows.update(existing.tab.windowId" in background
    assert "reused: false" in background
    assert "reused: true" in background
