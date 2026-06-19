from __future__ import annotations

import re

from app.schemas.resume import EducationItem, ProjectExperience, WorkExperience
from app.services.resume_skill_lexicon import (
    KNOWN_RESUME_SKILLS as ALL_KNOWN_RESUME_SKILLS,
    canonicalize_resume_skill_token,
    extract_resume_skills,
)


SECTION_KEYS = ["summary", "skills", "education", "experience", "projects", "certificates"]

SECTION_HEADINGS: dict[str, list[str]] = {
    "skills": [
        "skills",
        "technical skills",
        "technical stack",
        "skill set",
        "programming",
        "skills and tools",
        "技能",
        "技能栏",
        "专业技能",
        "技术栈",
        "技术技能",
    ],
    "education": [
        "education",
        "academic background",
        "education background",
        "教育",
        "教育经历",
        "学历",
    ],
    "experience": [
        "experience",
        "work experience",
        "internship",
        "internship experience",
        "professional experience",
        "research experience",
        "employment",
        "经历",
        "实习经历",
        "工作经历",
        "科研经历",
        "实验室经历",
    ],
    "projects": [
        "projects",
        "project",
        "project experience",
        "selected projects",
        "project experience and research",
        "项目",
        "项目经历",
        "课程项目",
        "项目经验",
    ],
    "certificates": [
        "awards",
        "honors",
        "certificates",
        "certifications",
        "certificate / awards",
        "证书",
        "奖项",
        "荣誉",
    ],
}

KNOWN_RESUME_SKILLS = [
    skill for skill in ALL_KNOWN_RESUME_SKILLS if skill not in {"C", "R", "Go", "CAN"}
]

WORK_KEYWORDS = [
    "intern",
    "internship",
    "research assistant",
    "teaching assistant",
    "lab assistant",
    "software engineer intern",
    "backend engineer intern",
    "research experience",
    "professional experience",
    "company",
    "实习",
    "工作",
    "研究",
    "实验室",
    "负责",
    "团队",
    "维护 crm",
]

DEGREE_KEYWORDS = [
    "Bachelor",
    "B.S.",
    "BS",
    "BEng",
    "B.Eng.",
    "Master",
    "M.S.",
    "MS",
    "MSc",
    "PhD",
    "本科",
    "硕士",
    "博士",
]

HIGHLIGHT_KEYWORDS = [
    "completed",
    "implemented",
    "built",
    "deployed",
    "launched",
    "improved",
    "reduced",
    "accuracy",
    "validation accuracy",
    "confusion matrix",
    "error analysis",
    "latency",
    "throughput",
    "dataset",
    "research",
    "analysis",
    "meeting notes",
    "competitive landscape",
    "market size",
    "实现",
    "完成",
    "优化",
    "提升",
    "部署",
    "上线",
    "准确率",
    "延迟",
    "吞吐",
    "测试",
    "用户",
    "数据集",
    "会议纪要",
    "行业研究",
    "竞品",
]

METRIC_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?\s?%|\d+\s?(?:ms|s|APIs?|tests?|users?|samples?|cases?|clips?)|[0-9]+k)",
    re.IGNORECASE,
)

_PROJECT_DETAIL_PREFIXES = [
    "built",
    "used",
    "implemented",
    "analyzed",
    "prepared",
    "completed",
    "designed",
    "processed",
    "extracted",
    "applied",
    "evaluated",
    "collaborated",
    "cleaned",
    "trained",
    "practiced",
    "compared",
    "maintained",
    "recorded",
    "followed",
    "identified",
    "explored",
    "ran",
    "负责",
    "使用",
    "完成",
    "实现",
    "分析",
    "维护",
    "记录",
    "整理",
]


def split_resume_sections(resume_text: str) -> dict[str, list[str]]:
    sections = {key: [] for key in SECTION_KEYS}
    current_section = "summary"

    for raw_line in resume_text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue

        heading, inline_value = _detect_heading(line)
        if heading:
            current_section = heading
            if inline_value:
                sections[current_section].append(inline_value)
            continue

        sections[current_section].append(line)

    return {key: value for key, value in sections.items() if value}


def parse_skills_from_sections(
    sections: dict[str, list[str]],
    full_text: str,
) -> list[str]:
    found: list[str] = []
    skills_text = "\n".join(sections.get("skills", []))
    for token in _split_skill_tokens(skills_text):
        skill = canonicalize_resume_skill_token(token)
        if skill:
            found.append(skill)

    searchable_sections = [
        full_text,
        "\n".join(sections.get("summary", [])),
        "\n".join(sections.get("projects", [])),
        "\n".join(sections.get("experience", [])),
    ]
    for text in searchable_sections:
        found.extend(extract_resume_skills(text))

    return _dedupe(found)


def parse_education_from_sections(
    sections: dict[str, list[str]],
) -> list[EducationItem]:
    education_lines = _section_lines(sections, "education")
    if not education_lines:
        education_lines = [
            line
            for line in _all_lines(sections)
            if _looks_like_education_line(line)
        ]

    return [_parse_education_line(line) for line in education_lines[:3]]


def parse_work_experience_from_sections(
    sections: dict[str, list[str]],
) -> list[WorkExperience]:
    experience_lines = _section_lines(sections, "experience")
    candidate_lines = experience_lines or [
        line
        for line in _all_lines(sections)
        if _contains_any(line, WORK_KEYWORDS) and not _looks_like_target_role_line(line)
    ]

    work_items: list[WorkExperience] = []
    for line in candidate_lines:
        if not experience_lines and not _contains_any(line, WORK_KEYWORDS):
            continue
        if _looks_like_target_role_line(line):
            continue
        role, company = _extract_role_company(line)
        work_items.append(
            WorkExperience(
                company=company,
                role=role,
                description=line,
                technologies=extract_resume_skills(line),
                raw_text=line,
            )
        )

    return work_items[:3]


def parse_projects_from_sections(
    sections: dict[str, list[str]],
) -> list[ProjectExperience]:
    project_lines = _section_lines(sections, "projects")
    if not project_lines:
        project_lines = [
            line
            for line in _all_lines(sections)
            if _looks_like_project_line(line)
        ]

    grouped_project_lines = _group_project_lines(project_lines)
    projects: list[ProjectExperience] = []
    for raw_text in grouped_project_lines[:3]:
        name, description = _extract_project_name_description(raw_text)
        projects.append(
            ProjectExperience(
                name=name or f"Project {len(projects) + 1}",
                description=description or raw_text,
                technologies=extract_resume_skills(raw_text),
                highlights=_extract_highlight_lines(raw_text.splitlines()),
                raw_text=raw_text,
            )
        )

    return projects


def parse_certificates_from_sections(
    sections: dict[str, list[str]],
) -> list[str]:
    certificate_lines = _section_lines(sections, "certificates")
    if not certificate_lines:
        certificate_lines = [
            line
            for line in _all_lines(sections)
            if _contains_any(
                line,
                [
                    "certificate",
                    "certification",
                    "award",
                    "honor",
                    "CET",
                    "证书",
                    "奖项",
                    "荣誉",
                ],
            )
        ]
    return certificate_lines[:5]


def extract_highlights_from_sections(
    sections: dict[str, list[str]],
    full_text: str,
) -> list[str]:
    lines = _all_lines(sections)
    highlights = _extract_highlight_lines(lines)
    if not highlights:
        highlights = _extract_highlight_lines(full_text.splitlines())
    return highlights[:5]


def _detect_heading(line: str) -> tuple[str | None, str | None]:
    normalized = _normalize_heading_text(line)
    prefix, inline_value = _split_heading_value(line)

    for key, headings in SECTION_HEADINGS.items():
        normalized_headings = {_normalize_heading_text(heading) for heading in headings}
        if normalized in normalized_headings:
            return key, None
        if prefix and _normalize_heading_text(prefix) in normalized_headings:
            return key, inline_value

    return None, None


def _split_heading_value(line: str) -> tuple[str | None, str | None]:
    for delimiter in [":", "："]:
        if delimiter in line:
            prefix, value = line.split(delimiter, 1)
            if len(prefix.strip()) <= 40:
                return prefix.strip(), value.strip() or None
    return None, None


def _normalize_heading_text(text: str) -> str:
    text = text.strip().strip(":：")
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def _clean_line(line: str) -> str:
    return line.strip().strip("-*•").strip()


def _split_skill_tokens(text: str) -> list[str]:
    return [
        token.strip()
        for token in re.split(r"[,;；，|/]", text)
        if token.strip()
    ]


def _section_lines(sections: dict[str, list[str]], key: str) -> list[str]:
    return [line for line in sections.get(key, []) if line.strip()]


def _all_lines(sections: dict[str, list[str]]) -> list[str]:
    lines: list[str] = []
    for key in SECTION_KEYS:
        lines.extend(sections.get(key, []))
    return lines


def _looks_like_education_line(line: str) -> bool:
    return _contains_any(
        line,
        [
            "education",
            "university",
            "college",
            "bachelor",
            "master",
            "phd",
            "B.S.",
            "M.S.",
            "学校",
            "大学",
            "学院",
            "本科",
            "硕士",
            "博士",
        ],
    )


def _looks_like_target_role_line(line: str) -> bool:
    prefix, _value = _split_heading_value(line)
    if not prefix:
        return False
    return _normalize_heading_text(prefix) in {
        "target role",
        "target roles",
        "target direction",
        "target directions",
        "desired role",
        "desired roles",
    }


def _parse_education_line(line: str) -> EducationItem:
    degree = _first_match(line, DEGREE_KEYWORDS)
    school = _extract_school(line)
    major = _extract_major(line)
    return EducationItem(
        school=school,
        degree=degree,
        major=major,
        raw_text=line,
    )


def _extract_school(line: str) -> str | None:
    parts = [part.strip() for part in re.split(r"[,，;；]", line) if part.strip()]
    for part in reversed(parts):
        if re.search(r"\b(?:University|College|Institute)\b", part):
            return part
        if re.fullmatch(r"[A-Z]{2,}(?:\s+[A-Z]{2,})?", part):
            return part

    school_match = re.search(
        r"([A-Z][A-Za-z&,\s]+(?:University|College|Institute)(?: of [A-Z][A-Za-z\s]+)?)",
        line,
    )
    if school_match:
        return school_match.group(1).strip(" ,")
    chinese_match = re.search(r"([\u4e00-\u9fff]{2,}(?:大学|学院))", line)
    if chinese_match:
        return chinese_match.group(1)
    return None


def _extract_major(line: str) -> str | None:
    in_match = re.search(r"\bin\s+([^,;，；]+)", line, re.IGNORECASE)
    if in_match:
        return in_match.group(1).strip()
    degree_major_match = re.search(
        r"(?:B\.S\.|M\.S\.|BS|MS|MSc|BEng|B\.Eng\.|Bachelor|Master|PhD)\s+([^,;，；]+)",
        line,
        re.IGNORECASE,
    )
    if degree_major_match:
        return degree_major_match.group(1).strip()
    parts = [part.strip() for part in re.split(r"[,，;；]", line) if part.strip()]
    for part in parts:
        if not _contains_any(part, DEGREE_KEYWORDS) and not _extract_school(part):
            return part
    return None


def _extract_role_company(line: str) -> tuple[str | None, str | None]:
    at_match = re.search(r"(.+?)\s+at\s+([^,;，；]+)", line, re.IGNORECASE)
    if at_match:
        return at_match.group(1).strip(), at_match.group(2).strip()
    comma_parts = [part.strip() for part in re.split(r"[,，]", line) if part.strip()]
    if len(comma_parts) >= 2 and _contains_any(comma_parts[0], WORK_KEYWORDS):
        return comma_parts[0], comma_parts[1]
    return None, None


def _looks_like_project_line(line: str) -> bool:
    return _contains_any(
        line,
        [
            "project",
            "system",
            "platform",
            "application",
            "agent",
            "demo",
            "prototype",
            "benchmark",
            "analysis tool",
            "research",
            "项目",
            "系统",
            "平台",
            "应用",
            "原型",
            "实验",
        ],
    )


def _extract_project_name_description(text: str) -> tuple[str | None, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, text

    prefix, value = _split_heading_value(lines[0])
    if prefix and _normalize_heading_text(prefix) in {
        "project",
        "projects",
        "项目",
        "项目经历",
    } and value:
        title, description = _split_title_description(value)
        return title, description

    if len(lines) == 1:
        return _split_title_description(lines[0])

    title = lines[0]
    description = " ".join(lines[1:]).strip()
    return title, description or title


def _split_title_description(text: str) -> tuple[str | None, str]:
    cleaned = text.strip()
    for separator in [". ", " - ", " – ", " — ", "：", ": ", "。"]:
        if separator in cleaned:
            title, rest = cleaned.split(separator, 1)
            if 3 <= len(title.strip()) <= 80:
                return title.strip(), rest.strip() or cleaned
    if len(cleaned) <= 80:
        return cleaned, cleaned
    return None, cleaned


def _group_project_lines(lines: list[str]) -> list[str]:
    groups: list[str] = []
    current_title: str | None = None
    current_details: list[str] = []

    for line in lines:
        if _looks_like_project_title(line):
            if current_title is not None:
                groups.append(_join_project_group(current_title, current_details))
            current_title = line
            current_details = []
            continue

        if current_title is None:
            current_title = line
        else:
            current_details.append(line)

    if current_title is not None:
        groups.append(_join_project_group(current_title, current_details))
    return groups


def _looks_like_project_title(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned or len(cleaned) > 90:
        return False
    if METRIC_PATTERN.search(cleaned):
        return False
    if _looks_like_detail_line(cleaned):
        return False
    word_count = len(re.findall(r"[A-Za-z0-9+#./-]+|[\u4e00-\u9fff]+", cleaned))
    return word_count <= 10


def _looks_like_detail_line(line: str) -> bool:
    lowered = line.lower()
    return any(lowered.startswith(prefix) for prefix in _PROJECT_DETAIL_PREFIXES)


def _join_project_group(title: str, details: list[str]) -> str:
    if not details:
        return title
    return "\n".join([title, *details])


def _extract_highlight_lines(lines: list[str]) -> list[str]:
    return _dedupe(
        [
            _clean_line(line)
            for line in lines
            if _clean_line(line)
            and (
                METRIC_PATTERN.search(line)
                or _contains_any(line, HIGHLIGHT_KEYWORDS)
            )
        ]
    )


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _first_match(text: str, keywords: list[str]) -> str | None:
    for keyword in keywords:
        if keyword.lower() in text.lower():
            return keyword
    return None


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
