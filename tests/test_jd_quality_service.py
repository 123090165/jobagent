"""回归验证jd quality service的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from app.services.jd_quality_service import evaluate_jd_quality


def test_evaluate_jd_quality_classifies_full_jd() -> None:
    jd_text = (
        "公司：安克创新\n"
        "地点：深圳\n"
        "工作性质：全职\n"
        "岗位职责：\n"
        "- 负责 AI 与生理信号相关算法系统研发。\n"
        "- 参与 PyTorch 模型训练、评估与部署。\n"
        "任职要求：\n"
        "- 熟悉 Python、PyTorch、深度学习、信号处理。\n"
        "- 具备本科及以上学历和良好工程实践。\n"
        + ("更多岗位细节。" * 120)
    )

    report = evaluate_jd_quality(jd_text, title="AI 算法工程师", source_url="https://example.com/jobs/1")

    assert report.quality_label == "full_jd"
    assert report.quality_score >= 0.75
    assert report.is_full_jd is True
    assert report.is_valid_jd is True
    assert "contains_responsibility_section" in report.evidence
    assert "contains_requirement_section" in report.evidence


def test_evaluate_jd_quality_classifies_external_link_only() -> None:
    jd_text = (
        "岗位详情见：https://mp.weixin.qq.com/s/example\n"
        "请查看外部链接获取完整说明。"
    )

    report = evaluate_jd_quality(jd_text, title="小鹏汽车校招")

    assert report.quality_label == "external_link_only"
    assert report.is_valid_jd is True
    assert "external_detail_link_only" in report.warnings
    assert report.external_links == ["https://mp.weixin.qq.com/s/example"]
    assert "contains_external_link" in report.evidence


def test_evaluate_jd_quality_classifies_snippet_only() -> None:
    jd_text = (
        "标题：研究助理\n"
        "公司：东北证券\n"
        "地点：深圳\n"
        "发布时间：2026-06-03\n"
        "欢迎投递，待遇面议，简历请发邮箱。"
    )

    report = evaluate_jd_quality(jd_text, title="研究助理")

    assert report.quality_label == "snippet_only"
    assert report.is_valid_jd is True
    assert "summary_without_jd_sections" in report.warnings


def test_evaluate_jd_quality_classifies_invalid_access_page() -> None:
    report = evaluate_jd_quality("请登录后查看职位详情，当前页面需要验证码。")

    assert report.quality_label == "invalid"
    assert report.is_valid_jd is False
    assert "possible_access_or_error_page" in report.warnings


def test_evaluate_jd_quality_classifies_invalid_short_text() -> None:
    report = evaluate_jd_quality("短文本")

    assert report.quality_label == "invalid"
    assert report.is_valid_jd is False
    assert "jd_text_empty_or_too_short" in report.warnings


def test_evaluate_jd_quality_classifies_partial_jd() -> None:
    jd_text = (
        "岗位职责：参与 Python 数据平台建设。\n"
        "需要支持部分模型部署和接口维护。\n"
        "欢迎熟悉 AI 工程流程的同学投递。"
    )

    report = evaluate_jd_quality(jd_text, title="AI 平台实习生")

    assert report.quality_label == "partial_jd"
    assert report.is_valid_jd is True
    assert report.is_full_jd is False


def test_evaluate_jd_quality_extracts_multiple_external_links() -> None:
    jd_text = (
        "详情见 https://mp.weixin.qq.com/s/example 和 https://docs.qq.com/doc/example 。"
        "完整岗位说明请查看外链。"
    )

    report = evaluate_jd_quality(jd_text)

    assert len(report.external_links) == 2
    assert "https://mp.weixin.qq.com/s/example" in report.external_links
    assert "https://docs.qq.com/doc/example" in report.external_links


def test_evaluate_jd_quality_records_evidence() -> None:
    jd_text = (
        "地点：深圳\n"
        "岗位职责：负责 AI 算法开发。\n"
        "任职要求：熟悉 Python 与机器学习。"
        + ("补充说明" * 80)
    )

    report = evaluate_jd_quality(jd_text, title="算法工程师")

    assert "contains_responsibility_section" in report.evidence
    assert "contains_requirement_section" in report.evidence
    assert "contains_skill_keywords" in report.evidence
