from pathlib import Path


WEB_SRC = Path("web/src")


def _read(relative_path: str) -> str:
    return (WEB_SRC / relative_path).read_text(encoding="utf-8")


def test_job_search_page_uses_persisted_candidate_pool_and_progressive_disclosure() -> None:
    page = _read("pages/JobSearchPage.vue")
    api = _read("api/profileSessions.ts")
    store = _read("stores/profileSession.ts")

    assert "/api/v1/job-search-runs/${runId}/items" in api
    assert "loadJobSearchItems" in store
    assert "Candidate pool" in page
    assert "Run diagnostics" in page
    assert "Full details" in page
    assert "Unscored candidates can be inspected, but cannot be saved yet." in page
    assert "Save selected" in page
    assert "BULK_LIMIT = 50" in page


def test_saved_jobs_page_exposes_bounded_selection_actions() -> None:
    page = _read("pages/SavedJobsPage.vue")

    assert "Select jobs" in page
    assert "Update status" in page
    assert "Archive" in page
    assert "Delete permanently" in page
    assert "BULK_LIMIT = 50" in page
    assert "window.confirm" in page
