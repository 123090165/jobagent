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
    assert "/api/v1/browser/job-captures/analyze" in background
    assert "capture.analysis_mode = requestedAnalysisMode" in background
    assert "capture.llm_provider = requestedLlmProvider" in background
    assert "CURRENT_PAGE_MIN_TEXT_LENGTH = 80" in background
    assert "Generic visible-text extractor was used" in background
    assert "chrome.sidePanel.setPanelBehavior" in background


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

    assert "Backend URL" in html
    assert "Profile session ID" in html
    assert "Analyze current job" in html
    assert "chrome.storage.local" in script
    assert "chrome.runtime.sendMessage" in script
    assert 'analysisMode: useLlmInput.checked ? "llm" : "deterministic"' in script
    assert 'llmProvider: "deepseek"' in script
    assert "stored.useLlm !== false" in script
    assert "chrome.permissions.request" in script
    assert "chrome.permissions.remove" in script
    assert "https://www.zhipin.com/*" in script
    assert "Capturing the current page" in script
    assert "Analysis complete" in script
    assert "errorType" in script
    assert "Matched strengths" in script
    assert "Critical gaps" in script
