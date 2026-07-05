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
    assert manifest["side_panel"]["default_path"] == "sidepanel.html"
    assert "http://127.0.0.1:8000/*" in manifest["host_permissions"]
    assert "http://localhost:8000/*" in manifest["host_permissions"]
    assert "<all_urls>" not in manifest.get("host_permissions", [])


def test_browser_helper_background_supports_user_triggered_current_page_capture() -> None:
    background = _read("browser-helper/background.js")

    assert "analyzeCurrentJob" in background
    assert "chrome.tabs.query({ active: true, currentWindow: true })" in background
    assert "chrome.scripting.executeScript" in background
    assert "captureCurrentJobPage" in background
    assert "document.body?.innerText" in background
    assert "/api/v1/browser/job-captures/analyze" in background
    assert "CURRENT_PAGE_MIN_TEXT_LENGTH = 80" in background
    assert "Generic visible-text extractor was used" in background
    assert "chrome.sidePanel.setPanelBehavior" in background


def test_browser_helper_side_panel_exposes_required_states_and_settings() -> None:
    html = _read("browser-helper/sidepanel.html")
    script = _read("browser-helper/sidepanel.js")

    assert "Backend URL" in html
    assert "Profile session ID" in html
    assert "Analyze current job" in html
    assert "chrome.storage.local" in script
    assert "chrome.runtime.sendMessage" in script
    assert "Capturing the current page" in script
    assert "Analysis complete" in script
    assert "errorType" in script
    assert "Matched strengths" in script
    assert "Critical gaps" in script
