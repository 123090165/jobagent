from __future__ import annotations

from pathlib import Path

from app.schemas.cuhksz_career import CUHKSZJobListItem
from app.services.cuhksz_career_service import (
    build_cuhksz_job_detail,
    convert_cuhksz_detail_to_search_result,
    evaluate_cuhksz_jd_quality,
    extract_cuhksz_jd_text,
    parse_cuhksz_job_list,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_parse_cuhksz_job_list_parses_items() -> None:
    items = parse_cuhksz_job_list(
        read_fixture("cuhksz_job_list_sample.html"),
        "https://career.cuhk.edu.cn/job/search/d_category/102",
    )

    assert len(items) == 2
    first = items[0]
    assert first.title == "AI 平台实习生"
    assert first.company == "深圳示例科技有限公司"
    assert first.location == "广东省 - 深圳市"
    assert first.job_type == "实习"
    assert first.education == "不限"
    assert first.published_at == "2026-05-30"
    assert first.deadline == "2026-07-01"
    assert first.detail_url == "https://career.cuhk.edu.cn/job/view/id/468293"
    assert first.external_id == "468293"


def test_parse_cuhksz_job_list_extracts_external_id_from_absolute_url() -> None:
    items = parse_cuhksz_job_list(
        read_fixture("cuhksz_job_list_sample.html"),
        "https://career.cuhk.edu.cn/job/search/d_category/102",
    )

    assert items[1].external_id == "468294"


def test_extract_cuhksz_jd_text_removes_navigation_and_extracts_body() -> None:
    jd_text, warnings = extract_cuhksz_jd_text(read_fixture("cuhksz_job_detail_sample.html"))

    assert "岗位职责" in jd_text
    assert "任职要求" in jd_text
    assert "Python" in jd_text
    assert "window.alert" not in jd_text
    assert "登录" not in jd_text
    assert warnings == []


def test_evaluate_cuhksz_jd_quality_scores_complete_jd() -> None:
    jd_text, _ = extract_cuhksz_jd_text(read_fixture("cuhksz_job_detail_sample.html"))

    is_full_jd, confidence, warnings = evaluate_cuhksz_jd_quality(jd_text)

    assert is_full_jd is True
    assert confidence >= 0.6
    assert "jd_text_too_short" not in warnings


def test_evaluate_cuhksz_jd_quality_warns_for_short_text() -> None:
    is_full_jd, confidence, warnings = evaluate_cuhksz_jd_quality("岗位职责：写 Python")

    assert is_full_jd is False
    assert confidence < 0.6
    assert "jd_text_too_short" in warnings


def test_build_cuhksz_job_detail_and_convert_to_search_result() -> None:
    list_item = CUHKSZJobListItem(
        external_id="468293",
        title="AI 平台实习生",
        company="深圳示例科技有限公司",
        location="广东省 - 深圳市",
        job_type="实习",
        education="不限",
        published_at="2026-05-30",
        deadline="2026-07-01",
        detail_url="https://career.cuhk.edu.cn/job/view/id/468293",
    )
    detail = build_cuhksz_job_detail(list_item, read_fixture("cuhksz_job_detail_sample.html"))
    result = convert_cuhksz_detail_to_search_result(detail)

    assert detail.is_full_jd is True
    assert detail.quality_label == "full_jd"
    assert detail.snippet
    assert result.source == "cuhksz_career"
    assert result.title == "AI 平台实习生"
    assert result.company == "深圳示例科技有限公司"
    assert result.jd_text is not None
    assert result.quality_label == "full_jd"
