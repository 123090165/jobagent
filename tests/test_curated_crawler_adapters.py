from __future__ import annotations

from app.services.job_search_providers.adapters.greenhouse_adapter import GreenhouseAdapter
from app.services.job_search_providers.adapters.lever_adapter import LeverAdapter


GREENHOUSE_LISTING_URL = "https://boards.greenhouse.io/acme"
GREENHOUSE_DETAIL_URL = "https://boards.greenhouse.io/acme/jobs/123"
GREENHOUSE_LISTING_HTML = """
<div class="opening">
  <a href="/acme/jobs/123">
    <div data-qa="job-name">Backend Engineer</div>
    <div data-qa="job-location">Tokyo / Remote</div>
  </a>
</div>
"""
GREENHOUSE_DETAIL_HTML = """
<div id="content">
  <p>Build FastAPI services, Python APIs, and backend automation for hiring systems.</p>
</div>
"""

LEVER_LISTING_URL = "https://jobs.lever.co/acme"
LEVER_DETAIL_URL = "https://jobs.lever.co/acme/backend-engineer"
LEVER_LISTING_HTML = """
<div class="posting">
  <a href="/acme/backend-engineer">
    <h5 data-qa="posting-name">Platform Engineer</h5>
    <span class="sort-by-location posting-category small-category-label">Remote</span>
  </a>
</div>
"""
LEVER_DETAIL_HTML = """
<div class="posting-page">
  <p>Own CI pipelines, Docker workflows, and internal platform reliability improvements.</p>
</div>
"""


def test_greenhouse_adapter_parses_fixture_html() -> None:
    adapter = GreenhouseAdapter(
        listing_urls=[GREENHOUSE_LISTING_URL],
        listing_pages={GREENHOUSE_LISTING_URL: GREENHOUSE_LISTING_HTML},
        detail_pages={GREENHOUSE_DETAIL_URL: GREENHOUSE_DETAIL_HTML},
    )

    candidates = adapter.search_jobs(query="backend engineer", location="Tokyo", limit=5)

    assert len(candidates) == 1
    assert candidates[0].title == "Backend Engineer"
    assert candidates[0].location == "Tokyo / Remote"
    detailed = adapter.fetch_job_detail(candidates[0])
    assert "FastAPI services" in (detailed.raw_description or "")


def test_lever_adapter_parses_fixture_html() -> None:
    adapter = LeverAdapter(
        listing_urls=[LEVER_LISTING_URL],
        listing_pages={LEVER_LISTING_URL: LEVER_LISTING_HTML},
        detail_pages={LEVER_DETAIL_URL: LEVER_DETAIL_HTML},
    )

    candidates = adapter.search_jobs(query="platform engineer", location="Remote", limit=5)

    assert len(candidates) == 1
    assert candidates[0].title == "Platform Engineer"
    assert candidates[0].location == "Remote"
    detailed = adapter.fetch_job_detail(candidates[0])
    assert "Docker workflows" in (detailed.raw_description or "")
