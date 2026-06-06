from __future__ import annotations

from pathlib import Path

from app.services.live_job.parsers.cuhksz import CUHKSZParser, extract_cuhksz_detail_text

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_cuhksz_parser_parse_list_extracts_expected_fields() -> None:
    parser = CUHKSZParser()

    items = parser.parse_list(
        read_fixture("cuhksz_job_list_sample.html"),
        "https://career.cuhk.edu.cn/job/search/d_category/102",
    )

    assert len(items) == 2
    first = items[0]
    assert first.source == "cuhksz_career"
    assert first.title == "AI 平台实习生"
    assert first.company == "深圳示例科技有限公司"
    assert first.location == "广东省 - 深圳市"
    assert first.job_type == "实习"
    assert first.education == "不限"
    assert first.external_id == "468293"
    assert first.detail_url == "https://career.cuhk.edu.cn/job/view/id/468293"


def test_cuhksz_parser_parse_detail_extracts_clean_full_jd() -> None:
    parser = CUHKSZParser()
    item = parser.parse_list(
        read_fixture("cuhksz_job_list_sample.html"),
        "https://career.cuhk.edu.cn/job/search/d_category/102",
    )[0]

    detail = parser.parse_detail(read_fixture("cuhksz_job_detail_sample.html"), item)

    assert "岗位职责" in detail.jd_text
    assert "任职要求" in detail.jd_text
    assert "Python" in detail.jd_text
    assert "window.alert" not in detail.jd_text
    assert "登录" not in detail.jd_text
    assert detail.quality_label == "full_jd"
    assert detail.confidence >= 0.6
    assert detail.is_full_jd is True


def test_extract_cuhksz_detail_text_removes_chinese_navigation_terms() -> None:
    html = """
    <html>
      <body>
        <nav>登录</nav>
        <header>关于我们</header>
        <div class="content">
          登录
          注册
          岗位职责
          负责 Python 后端开发。
          任职要求
          熟悉 FastAPI。
          香港中文大学（深圳）© 版权所有
        </div>
      </body>
    </html>
    """

    text, warnings = extract_cuhksz_detail_text(html)

    assert "岗位职责" in text
    assert "Python" in text
    assert "任职要求" in text
    assert "登录" not in text
    assert "注册" not in text
    assert "关于我们" not in text
    assert "版权所有" not in text
    assert warnings == []
