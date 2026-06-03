from __future__ import annotations

from pathlib import Path

from app.schemas.cuhksz_career import CUHKSZJobDetail, CUHKSZJobListItem
from app.services.public_job_storage_service import save_public_job_post
from app.services.search_providers.local_public_job_provider import LocalPublicJobProvider


def _build_detail(
    *,
    external_id: str = "468293",
    title: str = "AI Platform Intern",
    company: str = "Example Tech",
    location: str = "Shenzhen",
    jd_text: str | None = None,
    is_full_jd: bool = True,
    confidence: float = 0.88,
    quality_label: str = "full_jd",
    warnings: list[str] | None = None,
    external_links: list[str] | None = None,
) -> CUHKSZJobDetail:
    text = jd_text or (
        "Responsibilities:\n"
        "- Build Python and FastAPI services for internal workflows.\n"
        "- Maintain data ingestion and SQL-backed APIs.\n"
        "Requirements:\n"
        "- Strong Python backend fundamentals.\n"
        "- Comfort with SQL, testing, and LLM product ideas.\n"
        "Skills: Python, FastAPI, SQL, LLM"
    )
    return CUHKSZJobDetail(
        list_item=CUHKSZJobListItem(
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            job_type="Intern",
            education="Bachelor",
            published_at="2026-05-30",
            deadline="2026-07-01",
            detail_url=f"https://career.cuhk.edu.cn/job/view/id/{external_id}",
        ),
        jd_text=text,
        snippet=text[:120],
        is_full_jd=is_full_jd,
        confidence=confidence,
        quality_label=quality_label,
        warnings=warnings or [],
        external_links=external_links or [],
    )


def test_local_public_job_provider_returns_normalized_search_results(tmp_path: Path) -> None:
    database_path = tmp_path / "public-jobs.sqlite3"
    save_public_job_post(_build_detail(), database_path=database_path)

    provider = LocalPublicJobProvider(database_path=database_path)
    result = provider.search_jobs("AI Platform", limit=5)

    assert result.provider == "local_db"
    assert result.query == "AI Platform"
    assert len(result.items) == 1

    item = result.items[0]
    assert item.title == "AI Platform Intern"
    assert item.source == "cuhksz_career"
    assert item.url == "https://career.cuhk.edu.cn/job/view/id/468293"
    assert item.jd_text is not None
    assert item.is_full_jd is True
    assert item.confidence == 0.88
    assert item.quality_label == "full_jd"
    assert item.responsibilities
    assert item.requirements
    assert item.skills[:4] == ["Python", "FastAPI", "SQL", "LLM"]


def test_local_public_job_provider_applies_keyword_filter_and_limit(tmp_path: Path) -> None:
    database_path = tmp_path / "public-jobs.sqlite3"
    save_public_job_post(_build_detail(external_id="468293", title="AI Platform Intern"), database_path=database_path)
    save_public_job_post(
        _build_detail(
            external_id="468294",
            title="Backend Engineer",
            jd_text=(
                "Responsibilities:\n"
                "- Build internal APIs.\n"
                "Requirements:\n"
                "- Strong HTTP and testing fundamentals.\n"
                "Skills: Python, HTTP, Testing"
            ),
        ),
        database_path=database_path,
    )

    provider = LocalPublicJobProvider(database_path=database_path)

    ai_results = provider.search_jobs("AI Platform", limit=5)
    limited_results = provider.search_jobs("Engineer", limit=1)

    assert len(ai_results.items) == 1
    assert ai_results.items[0].title == "AI Platform Intern"
    assert len(limited_results.items) == 1
    assert limited_results.items[0].title == "Backend Engineer"


def test_local_public_job_provider_prioritizes_full_jd_over_external_link_only(tmp_path: Path) -> None:
    database_path = tmp_path / "public-jobs.sqlite3"
    save_public_job_post(
        _build_detail(
            external_id="468293",
            title="AI Engineer",
            quality_label="external_link_only",
            is_full_jd=False,
            confidence=0.42,
            jd_text="详情见 https://mp.weixin.qq.com/s/example ，请查看外部链接。",
            warnings=["external_detail_link_only"],
            external_links=["https://mp.weixin.qq.com/s/example"],
        ),
        database_path=database_path,
    )
    save_public_job_post(
        _build_detail(
            external_id="468294",
            title="AI Engineer",
            quality_label="full_jd",
            is_full_jd=True,
            confidence=0.88,
        ),
        database_path=database_path,
    )

    provider = LocalPublicJobProvider(database_path=database_path)
    result = provider.search_jobs("AI Engineer", limit=2)

    assert [item.quality_label for item in result.items] == ["full_jd", "external_link_only"]
