from __future__ import annotations

from pathlib import Path


WEB_SRC = Path(__file__).resolve().parents[1] / "web" / "src"


def test_saved_job_detail_presents_tasks_instead_of_internal_state_controls() -> None:
    page = (WEB_SRC / "pages" / "SavedJobDetailPage.vue").read_text(encoding="utf-8")

    assert "deriveJobNextStep" in page
    assert "Current task" in page
    assert "application-progress" in page
    assert "Start tracking" not in page
    assert "application.next_action" not in page
    assert "Application stage" not in page
    assert "Personal organization" in page
    assert "Open BOSS and generate message" in page


def test_next_step_rules_cover_the_primary_workspace_states() -> None:
    rules = (WEB_SRC / "domain" / "jobWorkspace.ts").read_text(encoding="utf-8")

    assert 'draft?.status === "generated"' in rules
    assert 'draft?.status === "approved"' in rules
    assert 'stage === "resume_requested" && resume === null' in rules
    assert 'resume?.status === "needs_review"' in rules
    assert 'stage === "interview"' in rules
    assert 'stage === "contacted" || stage === "resume_sent"' in rules
    assert 'stage === "closed"' in rules
    assert rules.index('stage === "closed"') < rules.index(
        'stage === "contacted" || stage === "resume_sent"'
    )
    assert "generate_greeting" in rules


def test_detail_refreshes_workspace_after_returning_from_browser_helper() -> None:
    page = (WEB_SRC / "pages" / "SavedJobDetailPage.vue").read_text(encoding="utf-8")

    assert 'window.addEventListener("focus", refreshAfterExternalFlow)' in page
    assert 'document.addEventListener("visibilitychange", refreshAfterExternalFlow)' in page
    assert "await store.loadJobDetail(job.value.saved_job_id)" in page
