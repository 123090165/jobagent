from __future__ import annotations

from pathlib import Path


WEB_SRC = Path(__file__).resolve().parents[1] / "web" / "src"


def test_assistant_page_loads_catalog_and_exposes_pinned_context_controls() -> None:
    page = (WEB_SRC / "pages" / "ChatPage.vue").read_text(encoding="utf-8")
    api = (WEB_SRC / "api" / "chat.ts").read_text(encoding="utf-8")

    assert "getChatContextCatalog" in page
    assert "/api/v1/chat/context-catalog" in api
    assert "browser_capture_ids" in page
    assert 'kind: "browser_capture"' in page
    assert "handleBrowserHelperContextUpdate" in page
    assert "JOBAGENT_HELPER_CONTEXT_UPDATED" in page
    assert "selectedProfileId" in page
    assert "selectedRunIds" in page
    assert "selectedSavedJobIds" in page
    assert "retainedResultRefs" in page
    assert "Use automatic" in page
    assert "Save context" in page
    assert "removePinnedContext" in page


def test_assistant_page_exposes_compact_usage_and_memory_composition() -> None:
    page = (WEB_SRC / "pages" / "ChatPage.vue").read_text(encoding="utf-8")
    api = (WEB_SRC / "api" / "chat.ts").read_text(encoding="utf-8")

    assert "getChatMemoryStatus" in page
    assert "/memory`" in api
    assert "Current memory" in page
    assert "Recent conversation" in page
    assert "Compressed summary" in page
    assert "Pinned context" in page
    assert "Previous answer references" in page
    assert "usageText(turn)" in page


def test_assistant_page_can_retry_a_fallback_turn_without_overwriting_the_draft() -> None:
    page = (WEB_SRC / "pages" / "ChatPage.vue").read_text(encoding="utf-8")

    assert "async function retryTurn(turn: ChatTurn)" in page
    assert "await sendQuestion(turn.question, false, turn.turn_id)" in page
    assert "turn.analysis_mode === 'fallback'" in page
    assert '@click="retryTurn(turn)"' in page
    assert "fallbackReasonText(turn)" in page


def test_resource_pages_create_global_assistant_conversations_with_pinned_context() -> None:
    search_page = (WEB_SRC / "pages" / "JobSearchPage.vue").read_text(encoding="utf-8")
    saved_page = (WEB_SRC / "pages" / "SavedJobDetailPage.vue").read_text(encoding="utf-8")

    assert "job_search_result_refs" in search_page
    assert "askAssistantAboutResult" in search_page
    assert "saved_job_ids" in saved_page
    assert "askAssistantAboutJob" in saved_page
    assert 'name: "assistant"' in search_page
    assert 'name: "assistant"' in saved_page


def test_assistant_page_pairs_a_scoped_browser_helper_session() -> None:
    page = (WEB_SRC / "pages" / "ChatPage.vue").read_text(encoding="utf-8")
    api = (WEB_SRC / "api" / "browserHelper.ts").read_text(encoding="utf-8")
    bridge = (WEB_SRC / "services" / "browserHelper.ts").read_text(encoding="utf-8")

    assert "Pair Browser Helper" in page
    assert "createBrowserHelperSession" in page
    assert "pingBrowserHelper" in page
    assert page.index("await pingBrowserHelper()") < page.index("await createBrowserHelperSession()")
    assert "getBrowserHelperConnectionStatus" in page
    assert "Browser Helper connected" in page
    assert 'route.query.pair_browser_helper === "1"' in page
    assert "/api/v1/browser-helper/sessions" in api
    assert 'action: "bindJobAgentSession"' in bridge
    assert 'action: "getBrowserHelperConnectionStatus"' in bridge


def test_assistant_page_uses_the_app_shell_viewport_without_negative_offset() -> None:
    page = (WEB_SRC / "pages" / "ChatPage.vue").read_text(encoding="utf-8")

    assert "height: calc(100dvh - var(--topbar-height))" in page
    assert "grid-template-columns: clamp(220px, 19vw, 260px)" in page
    assert "margin: -24px" not in page
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in page
