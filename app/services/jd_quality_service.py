from __future__ import annotations

import re
from typing import Iterable

from app.schemas.jd_quality import JDQualityReport

FULL_JD = "full_jd"
PARTIAL_JD = "partial_jd"
EXTERNAL_LINK_ONLY = "external_link_only"
SNIPPET_ONLY = "snippet_only"
INVALID_JD = "invalid"

RESPONSIBILITY_KEYWORDS = [
    "岗位职责",
    "工作职责",
    "工作内容",
    "你将参与",
    "职责",
    "responsibilities",
    "responsibility",
]
REQUIREMENT_KEYWORDS = [
    "职位要求",
    "任职要求",
    "岗位要求",
    "资格要求",
    "要求",
    "requirements",
    "requirement",
    "qualifications",
    "qualification",
]
SKILL_KEYWORDS = [
    "python",
    "java",
    "c++",
    "sql",
    "pytorch",
    "fastapi",
    "llm",
    "ai",
    "机器学习",
    "深度学习",
    "算法",
    "数据分析",
    "信号处理",
    "本科",
    "硕士",
]
METADATA_KEYWORDS = [
    "公司",
    "地点",
    "工作地点",
    "location",
    "工作性质",
    "招聘人数",
    "学历",
    "经验",
    "薪资",
    "base",
]
ACCESS_OR_ERROR_TERMS = [
    "请登录",
    "登录后查看",
    "验证码",
    "access denied",
    "forbidden",
    "403",
    "404",
    "页面不存在",
]
EXTERNAL_LINK_TERMS = [
    "详见",
    "详情见",
    "请查看",
    "mp.weixin.qq.com",
    "docs.qq.com",
    "jinshuju",
    "form",
    "问卷星",
]
EXTERNAL_LINK_HOST_HINTS = [
    "mp.weixin.qq.com",
    "docs.qq.com",
    "jinshuju",
    "wjx",
    "form",
]
URL_PATTERN = re.compile(r"https?://[^\s<>\")]+", re.IGNORECASE)


def evaluate_jd_quality(
    jd_text: str,
    title: str | None = None,
    source_url: str | None = None,
) -> JDQualityReport:
    text = (jd_text or "").strip()
    text_length = len(text)
    warnings: list[str] = []
    evidence: list[str] = []
    external_links = _extract_external_links(text)
    text_lower = text.lower()
    contains_responsibility = _contains_any(text_lower, RESPONSIBILITY_KEYWORDS)
    contains_requirement = _contains_any(text_lower, REQUIREMENT_KEYWORDS)
    contains_skill_keywords = _contains_any(text_lower, SKILL_KEYWORDS)
    contains_metadata = _contains_any(text_lower, METADATA_KEYWORDS) or bool(title) or bool(source_url)
    contains_external_link = bool(external_links)
    contains_external_link_cue = _contains_any(text_lower, EXTERNAL_LINK_TERMS)

    if _contains_any(text_lower, ACCESS_OR_ERROR_TERMS):
        warnings.append("possible_access_or_error_page")
        evidence.append("contains_access_or_error_terms")
        return _build_report(
            INVALID_JD,
            0.1,
            warnings=warnings,
            evidence=evidence,
            text_length=text_length,
            external_links=external_links,
        )

    if contains_responsibility:
        evidence.append("contains_responsibility_section")
    if contains_requirement:
        evidence.append("contains_requirement_section")
    if contains_skill_keywords:
        evidence.append("contains_skill_keywords")
    if contains_metadata:
        evidence.append("contains_metadata")
    if text_length >= 500:
        evidence.append("text_length>=500")
    if contains_external_link:
        evidence.append("contains_external_link")

    if text_length < 80:
        evidence.append("text_length<80")
        if (
            contains_external_link
            and (contains_external_link_cue or _contains_external_hosts(external_links))
        ):
            warnings.append("external_detail_link_only")
            return _build_report(
                EXTERNAL_LINK_ONLY,
                0.35,
                warnings=warnings,
                evidence=evidence,
                text_length=text_length,
                external_links=external_links,
            )
        if contains_responsibility or contains_requirement or contains_skill_keywords:
            warnings.append("jd_text_too_short")
            return _build_report(
                PARTIAL_JD,
                0.4,
                warnings=warnings,
                evidence=evidence,
                text_length=text_length,
                external_links=external_links,
            )
        if contains_metadata:
            warnings.append("summary_without_jd_sections")
            return _build_report(
                SNIPPET_ONLY,
                0.25,
                warnings=warnings,
                evidence=evidence,
                text_length=text_length,
                external_links=external_links,
            )
        warnings.append("jd_text_empty_or_too_short")
        return _build_report(
            INVALID_JD,
            0.05,
            warnings=warnings,
            evidence=evidence,
            text_length=text_length,
            external_links=external_links,
        )

    if (
        contains_external_link
        and (contains_external_link_cue or _contains_external_hosts(external_links))
        and (text_length < 400 or not (contains_responsibility and contains_requirement))
    ):
        warnings.append("external_detail_link_only")
        return _build_report(
            EXTERNAL_LINK_ONLY,
            0.45 if text_length >= 120 else 0.35,
            warnings=warnings,
            evidence=evidence,
            text_length=text_length,
            external_links=external_links,
        )

    if (
        text_length >= 500
        and contains_responsibility
        and contains_requirement
        and contains_metadata
        and contains_skill_keywords
    ):
        return _build_report(
            FULL_JD,
            0.85,
            warnings=warnings,
            evidence=evidence,
            text_length=text_length,
            external_links=external_links,
        )

    if text_length >= 200 and (contains_responsibility or contains_requirement or contains_skill_keywords):
        if not contains_responsibility:
            warnings.append("missing_responsibility_section")
        if not contains_requirement:
            warnings.append("missing_requirement_section")
        return _build_report(
            PARTIAL_JD,
            0.62 if contains_responsibility and contains_requirement else 0.55,
            warnings=warnings,
            evidence=evidence,
            text_length=text_length,
            external_links=external_links,
        )

    if not contains_responsibility and not contains_requirement:
        warnings.append("summary_without_jd_sections")
        return _build_report(
            SNIPPET_ONLY,
            0.3,
            warnings=warnings,
            evidence=evidence,
            text_length=text_length,
            external_links=external_links,
        )

    return _build_report(
        PARTIAL_JD,
        0.5,
        warnings=warnings,
        evidence=evidence,
        text_length=text_length,
        external_links=external_links,
    )


def _build_report(
    quality_label: str,
    quality_score: float,
    *,
    warnings: list[str],
    evidence: list[str],
    text_length: int,
    external_links: list[str],
) -> JDQualityReport:
    normalized_score = max(0.0, min(1.0, float(quality_score)))
    normalized_evidence = _dedupe_preserve_order(evidence)
    normalized_warnings = _dedupe_preserve_order(warnings)
    normalized_links = _dedupe_preserve_order(external_links)
    return JDQualityReport(
        quality_label=quality_label,
        quality_score=normalized_score,
        is_valid_jd=quality_label in {FULL_JD, PARTIAL_JD, EXTERNAL_LINK_ONLY, SNIPPET_ONLY},
        is_full_jd=quality_label == FULL_JD,
        warnings=normalized_warnings,
        evidence=normalized_evidence,
        text_length=text_length,
        external_links=normalized_links,
    )


def _extract_external_links(text: str) -> list[str]:
    return _dedupe_preserve_order([match.strip() for match in URL_PATTERN.findall(text or "") if match.strip()])


def _contains_external_hosts(external_links: list[str]) -> bool:
    lowered_links = [link.lower() for link in external_links]
    return any(hint in link for link in lowered_links for hint in EXTERNAL_LINK_HOST_HINTS)


def _contains_any(text: str, values: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(value.lower() in lowered for value in values)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = (value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
