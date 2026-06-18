from __future__ import annotations

from app.application.job_search_usecases import create_job_search_run, execute_job_search_run
from app.schemas.job_search import JobSearchRunCreateRequest
from app.services.job_search_providers.curated_crawler_provider import CuratedCrawlerProvider
from app.services.job_search_providers.adapters.greenhouse_adapter import GreenhouseAdapter
from app.services.job_search_providers.adapters.lever_adapter import LeverAdapter
from tests.test_job_search_live_api import _create_session_with_confirmed_profile


GREENHOUSE_URL = "https://boards.greenhouse.io/acme"
LEVER_URL = "https://jobs.lever.co/acme"


def _provider() -> CuratedCrawlerProvider:
    greenhouse = GreenhouseAdapter(
        listing_urls=[GREENHOUSE_URL],
        listing_pages={
            GREENHOUSE_URL: """
            <div class="opening">
              <a href="/acme/jobs/123">
                <div data-qa="job-name">Backend Engineer</div>
                <div data-qa="job-location">Tokyo</div>
              </a>
            </div>
            """
        },
        detail_pages={
            "https://boards.greenhouse.io/acme/jobs/123": """
            <div id="content"><p>Python FastAPI SQL APIs for product and internal tooling.</p></div>
            """
        },
    )
    lever = LeverAdapter(
        listing_urls=[LEVER_URL],
        listing_pages={
            LEVER_URL: """
            <div class="posting">
              <a href="/acme/platform-engineer">
                <h5 data-qa="posting-name">Platform Engineer</h5>
                <span class="sort-by-location posting-category small-category-label">Remote</span>
              </a>
            </div>
            """
        },
        detail_pages={
            "https://jobs.lever.co/acme/platform-engineer": """
            <div class="posting-page"><p>Docker CI platform reliability and developer productivity.</p></div>
            """
        },
    )
    return CuratedCrawlerProvider(
        adapters=[greenhouse, lever],
        allowlisted_domains=["boards.greenhouse.io", "jobs.lever.co"],
    )


def test_fake_curated_provider_returns_deterministic_jobs() -> None:
    provider = _provider()

    results = provider.search_jobs(query="engineer", location=None, limit=10)

    assert len(results) == 2
    assert all(item.source_provider == "curated_crawler" for item in results)
    assert any("Python FastAPI" in (item.raw_description or "") for item in results)


def test_live_job_search_with_curated_provider_records_trace(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-curated.sqlite3")
    provider = _provider()
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=confirmed["profile_session"]["session_id"],
            search_mode="live_search",
            search_provider="curated_crawler",
            use_llm=False,
            max_results=5,
        ),
        job_search_provider=provider,
    )

    completed = execute_job_search_run(
        run_response.job_search_run.job_search_run_id,
        job_search_provider=provider,
        max_results=5,
    )

    assert completed.job_search_run.status == "completed"
    provider_step = completed.steps[1]
    assert provider_step.mode == "provider"
    assert provider_step.summary == "Collected 2 candidates from curated_crawler."
