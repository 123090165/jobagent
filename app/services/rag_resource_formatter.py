"""把画像、搜索和收藏职位转换为可索引文本，同时控制敏感字段和长度。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.schemas.rag_sync import FormattedRAGResource
from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJob


_SENSITIVE_KEYS = frozenset({
    "email",
    "phone",
    "telephone",
    "mobile",
    "contact",
    "address",
    "password",
    "token",
})


def format_resume_profile(
    profile: ResumeProfile,
    *,
    resource_version: int,
) -> FormattedRAGResource:
    sections = [
        "[资源] 用户确认画像",
        f"[名称] {profile.name}",
        f"[摘要] {profile.summary}",
        _list_section("目标职位", profile.target_roles),
        _list_section("目标方向", profile.target_directions),
        _list_section("核心技能", profile.core_skills),
        _list_section("辅助技能", profile.supporting_skills),
        _list_section("搜索关键词", profile.search_keywords),
        _list_section("期望地点", profile.preferred_locations),
        _list_section("工作方式", profile.work_arrangements),
        _list_section("优势", profile.strengths),
        _list_section("风险与待确认项", profile.risks),
    ]
    structured_lines = _flatten_mapping(profile.profile)
    if structured_lines:
        sections.append("[结构化画像]\n" + "\n".join(structured_lines))
    return FormattedRAGResource(
        resource_type="resume_profile",
        resource_id=profile.resume_profile_id,
        resource_version=resource_version,
        title=profile.name,
        text="\n\n".join(section for section in sections if section),
        source_updated_at=profile.updated_at,
    )


def format_saved_job(
    job: SavedJob,
    *,
    resource_version: int,
) -> FormattedRAGResource:
    sections = [
        "[资源] 用户收藏职位",
        f"[职位] {job.title}",
        f"[公司] {job.company or '未提供'}",
        f"[地点] {job.location or '未提供'}",
        f"[薪资] {job.salary or '未提供'}",
        f"[雇佣类型] {job.employment_type or '未提供'}",
        _list_section("标签", job.tags),
        "[职位描述]\n" + job.raw_jd_text.strip(),
    ]
    structured_lines = _flatten_mapping(job.structured_jd)
    if structured_lines:
        sections.append("[结构化职位要求]\n" + "\n".join(structured_lines))
    return FormattedRAGResource(
        resource_type="saved_job",
        resource_id=job.saved_job_id,
        resource_version=resource_version,
        title=f"{job.title} - {job.company or '未知公司'}",
        text="\n\n".join(section for section in sections if section),
        source_updated_at=job.updated_at,
    )


def _list_section(label: str, values: Sequence[str]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return ""
    return f"[{label}]\n" + "\n".join(f"- {value}" for value in cleaned)


def _flatten_mapping(
    value: Mapping[str, Any],
    *,
    prefix: str = "",
) -> list[str]:
    lines: list[str] = []
    for key in sorted(value):
        normalized_key = str(key).strip()
        if not normalized_key or normalized_key.lower() in _SENSITIVE_KEYS:
            continue
        item = value[key]
        path = f"{prefix}.{normalized_key}" if prefix else normalized_key
        if isinstance(item, Mapping):
            lines.extend(_flatten_mapping(item, prefix=path))
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            for index, nested in enumerate(item):
                nested_path = f"{path}[{index}]"
                if isinstance(nested, Mapping):
                    lines.extend(_flatten_mapping(nested, prefix=nested_path))
                elif nested not in (None, ""):
                    lines.append(f"{nested_path}: {nested}")
        elif item not in (None, ""):
            lines.append(f"{path}: {item}")
    return lines
