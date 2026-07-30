"""回归验证cuhksz career provider的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from pathlib import Path

from app.application.job_search_usecases import create_job_search_run, execute_job_search_run
from app.schemas.job_search import JobSearchRunCreateRequest
from app.services.job_search_providers.cuhksz_career_provider import (
    CUHKSZ_CAREER_SEARCH_URL,
    MISSING_REQUIREMENTS_WARNING,
    NO_JD_SECTIONS_WARNING,
    NO_PROVIDER_MATCH_WARNING,
    SHORT_JD_WARNING,
    CUHKSZCareerProvider,
    _is_low_quality_candidate,
    build_cuhksz_search_url,
    build_cuhksz_title_terms,
)
from app.services.job_search_providers.base import RawJobCandidate
from tests.test_job_search_live_api import FakeJSONLLM, _create_session_with_confirmed_profile

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROVIDER_SOURCE = Path("app/services/job_search_providers/cuhksz_career_provider.py")
SIGNAL_NORMALIZER_SOURCE = Path("app/services/search_signal_normalizer.py")


def read_fixture(name: str) -> str:
    """提供 read_fixture 所需的测试行为。"""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_cuhksz_list_page_fixture_parsing_extracts_expected_fields() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
            "https://career.cuhk.edu.cn/job/view/id/468294": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )

    results = provider.search_jobs(query="AI", location=None, limit=5)

    assert len(results) == 2
    first = results[0]
    assert first.title
    assert first.company
    assert first.location
    assert first.source_provider == "cuhksz_career"
    assert first.source_url == "https://career.cuhk.edu.cn/job/view/id/468293"
    assert "Published 2026-05-30" in first.snippet or "Published Date" in (first.raw_description or "")


def test_cuhksz_search_url_uses_title_query_params() -> None:
    url = build_cuhksz_search_url("算法")

    assert url.startswith(CUHKSZ_CAREER_SEARCH_URL)
    assert "title=%E7%AE%97%E6%B3%95" in url
    assert "title_type=1" in url
    assert "d_industry=" in url
    assert "d_skill=" in url


def test_cuhksz_title_terms_adapt_preview_query_to_short_terms() -> None:
    query = "\u5065\u5eb7\u7b97\u6cd5\u5b9e\u4e60\u751f PPG ECG Python"
    terms = build_cuhksz_title_terms(query)

    assert terms[:4] == ["算法", "健康算法", "PPG", "ECG"]
    assert "Python" not in terms


def test_cuhksz_title_terms_translate_english_health_queries_to_chinese_broad_terms() -> None:
    assert build_cuhksz_title_terms("AI Health Algorithm Intern PPG ECG") == [
        "算法",
        "健康算法",
        "PPG",
        "ECG",
    ]
    assert build_cuhksz_title_terms("Physiological Signal Processing Intern PPG ECG") == [
        "生理信号",
        "PPG",
        "ECG",
    ]


def test_cuhksz_title_terms_use_chinese_for_common_english_role_queries() -> None:
    assert build_cuhksz_title_terms("Brand Marketing Intern market research Excel") == [
        "市场",
    ]
    assert build_cuhksz_title_terms("Speech Recognition Intern ASR Python") == [
        "语音识别",
        "ASR",
    ]


def test_cuhksz_provider_fetches_search_url_with_title_params() -> None:
    fetched_urls: list[str] = []

    def fetcher(url: str) -> str:
        fetched_urls.append(url)
        if "/job/view/id/" in url:
            return read_fixture("cuhksz_job_detail_sample.html")
        return read_fixture("cuhksz_job_list_sample.html")

    provider = CUHKSZCareerProvider(fetcher=fetcher)

    provider.search_jobs(query="算法", location=None, limit=1)

    assert fetched_urls[0].startswith(CUHKSZ_CAREER_SEARCH_URL)
    assert "title=%E7%AE%97%E6%B3%95" in fetched_urls[0]
    assert fetched_urls[0] != CUHKSZ_CAREER_SEARCH_URL


def test_cuhksz_provider_reuses_cached_fetches_for_same_url() -> None:
    fetched_urls: list[str] = []

    def fetcher(url: str) -> str:
        fetched_urls.append(url)
        if "/job/view/id/" in url:
            return read_fixture("cuhksz_job_detail_sample.html")
        return read_fixture("cuhksz_job_list_sample.html")

    provider = CUHKSZCareerProvider(fetcher=fetcher)

    provider.search_jobs(query="AI Health Algorithm Intern PPG ECG", location=None, limit=1)
    provider.search_jobs(query="AI Health Algorithm Intern PPG ECG", location=None, limit=1)

    assert len(fetched_urls) == 2
    assert any("title=%E7%AE%97%E6%B3%95" in url for url in fetched_urls)
    assert any("/job/view/id/" in url for url in fetched_urls)


def test_cuhksz_provider_keeps_candidates_without_provider_side_match() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )

    candidate = provider.search_jobs(query="speech recognition", location="Boston", limit=1)[0]

    assert candidate.source_url == "https://career.cuhk.edu.cn/job/view/id/468293"
    assert NO_PROVIDER_MATCH_WARNING in candidate.provider_warnings


def test_cuhksz_detail_page_parsing_extracts_description() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )

    candidate = provider.search_jobs(query="AI", location=None, limit=1)[0]

    assert candidate.raw_description is not None
    assert "Job Description:" in candidate.raw_description


def test_cuhksz_detail_preserves_responsibilities_and_requirements_in_page_order() -> None:
    source_url = "https://career.cuhk.edu.cn/job/view/id/468293"
    provider = CUHKSZCareerProvider(
        detail_pages={
            source_url: """
            <main>
              <h1>AI Intern</h1>
              <section><h2>Responsibilities</h2><p>Build signal-processing pipelines.</p></section>
              <section><h2>Qualifications</h2><p>Strong Python and statistics skills.</p></section>
              <section><h2>Responsibilities</h2><p>Build signal-processing pipelines.</p></section>
            </main>
            """,
        },
    )
    candidate = RawJobCandidate(
        title="AI Intern",
        company="Example Co",
        location="Shenzhen",
        source_url=source_url,
        source_provider="cuhksz_career",
        snippet="AI Intern",
    )

    detailed = provider.fetch_job_detail(candidate)

    assert detailed.raw_description is not None
    responsibilities_at = detailed.raw_description.index("Build signal-processing pipelines.")
    requirements_at = detailed.raw_description.index("Strong Python and statistics skills.")
    assert responsibilities_at < requirements_at
    assert detailed.raw_description.count("Build signal-processing pipelines.") == 1
    assert detailed.detail_status == "detail_fetched"


def test_cuhksz_short_detail_is_kept_with_completeness_warnings() -> None:
    source_url = "https://career.cuhk.edu.cn/job/view/id/468293"
    provider = CUHKSZCareerProvider(
        detail_pages={
            source_url: "<main><h1>AI Intern</h1><section><h2>Responsibilities</h2><p>Build models.</p></section></main>",
        },
    )
    candidate = RawJobCandidate(
        title="AI Intern",
        company="Example Co",
        location="Shenzhen",
        source_url=source_url,
        source_provider="cuhksz_career",
        snippet="AI Intern",
    )

    detailed = provider.fetch_job_detail(candidate)

    assert detailed.source_url == source_url
    assert detailed.raw_description is not None
    assert "Build models." in detailed.raw_description
    assert detailed.detail_status == "detail_fetched_incomplete"
    assert SHORT_JD_WARNING in detailed.provider_warnings
    assert MISSING_REQUIREMENTS_WARNING in detailed.provider_warnings
    assert NO_JD_SECTIONS_WARNING not in detailed.provider_warnings


def test_cuhksz_missing_jd_sections_uses_full_page_fallback_with_warning() -> None:
    source_url = "https://career.cuhk.edu.cn/job/view/id/468293"
    provider = CUHKSZCareerProvider(
        detail_pages={source_url: "<main><h1>AI Intern</h1><p>Contact recruiter.</p></main>"},
    )
    candidate = RawJobCandidate(
        title="AI Intern",
        company="Example Co",
        location="Shenzhen",
        source_url=source_url,
        source_provider="cuhksz_career",
        snippet="AI Intern",
    )

    detailed = provider.fetch_job_detail(candidate)

    assert detailed.source_url == source_url
    assert detailed.detail_status == "detail_fetched_incomplete"
    assert NO_JD_SECTIONS_WARNING in detailed.provider_warnings
    assert "Contact recruiter." in (detailed.raw_description or "")


def test_cuhksz_detail_generic_title_does_not_replace_list_metadata() -> None:
    source_url = "https://career.cuhk.edu.cn/job/view/id/468293"
    provider = CUHKSZCareerProvider(
        detail_pages={
            source_url: """
            <html>
              <body>
                <h1>招聘信息</h1>
                <p>公司名称：：</p>
                <p>工作地点：广东省 - 深圳市</p>
                <section>
                  <h2>岗位职责</h2>
                  <p>AI健康算法工程师实习生（生理信号方向），负责PPG和ECG信号处理。</p>
                </section>
              </body>
            </html>
            """,
        },
    )
    candidate = RawJobCandidate(
        title="安克创新AI健康算法工程师实习生（生理信号方向）",
        company="安克创新",
        location="广东省 - 深圳市",
        source_url=source_url,
        source_provider="cuhksz_career",
        snippet="安克创新 | 广东省 - 深圳市 | 实习",
    )

    detailed = provider.fetch_job_detail(candidate)

    assert detailed.title == "安克创新AI健康算法工程师实习生（生理信号方向）"
    assert detailed.company == "安克创新"
    assert detailed.source_url == source_url
    assert detailed.raw_description is not None
    assert "Title: 安克创新AI健康算法工程师实习生（生理信号方向）" in detailed.raw_description
    assert "Company: 安克创新" in detailed.raw_description
    assert "PPG" in detailed.raw_description
    assert _is_low_quality_candidate(detailed) is False


def test_cuhksz_low_quality_filter_keeps_candidates_with_missing_company() -> None:
    candidate = RawJobCandidate(
        title="AI健康算法工程师实习生（生理信号方向）",
        company=None,
        location="广东省 - 深圳市",
        source_url="https://career.cuhk.edu.cn/job/view/id/468293",
        source_provider="cuhksz_career",
        snippet="广东省 - 深圳市 | 实习",
    )

    assert _is_low_quality_candidate(candidate) is False


def test_cuhksz_detail_fetch_failure_keeps_candidate_with_warning() -> None:
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={},
        fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("boom")) if url != CUHKSZ_CAREER_SEARCH_URL else read_fixture("cuhksz_job_list_sample.html"),
    )

    candidate = provider.search_jobs(query="AI", location=None, limit=1)[0]

    assert candidate.raw_description is None
    assert candidate.provider_warnings
    assert candidate.source_url == "https://career.cuhk.edu.cn/job/view/id/468293"


def test_source_files_do_not_contain_mojibake_fragments() -> None:
    provider_source = PROVIDER_SOURCE.read_text(encoding="utf-8")
    signal_source = SIGNAL_NORMALIZER_SOURCE.read_text(encoding="utf-8")

    for fragment in ["鍏徃", "宸ヤ綔", "钖祫", "璇煶", "鐢熺悊", "鍙┛", "蹇冪數", "宓屽叆"]:
        assert fragment not in provider_source
        assert fragment not in signal_source

    assert 'COMPANY_LABELS = ["公司名称", "企业名称"]' in provider_source
    assert '"语音识别": ["speech recognition", "ASR", "automatic speech recognition"]' in signal_source


def test_live_search_use_case_works_with_fake_cuhksz_provider(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-cuhksz-provider.sqlite3")
    provider = CUHKSZCareerProvider(
        list_page_html=read_fixture("cuhksz_job_list_sample.html"),
        detail_pages={
            "https://career.cuhk.edu.cn/job/view/id/468293": read_fixture("cuhksz_job_detail_sample.html"),
            "https://career.cuhk.edu.cn/job/view/id/468294": read_fixture("cuhksz_job_detail_sample.html"),
        },
    )
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=confirmed["profile_session"]["session_id"],
            search_mode="live_search",
            search_provider="cuhksz_career",
            use_llm=True,
            max_results=5,
        ),
        job_search_provider=provider,
        llm_service=FakeJSONLLM(),
    )

    completed = execute_job_search_run(
        run_response.job_search_run.job_search_run_id,
        job_search_provider=provider,
        llm_service=FakeJSONLLM(),
        max_results=5,
    )

    assert completed.job_search_run.status == "completed"
    assert completed.job_search_run.search_provider == "cuhksz_career"
    assert "cuhksz_career" in completed.steps[1].summary
