from __future__ import annotations

import re

from app.schemas.resume import EducationItem, ProjectExperience, WorkExperience


SECTION_KEYS = ["summary", "skills", "education", "experience", "projects", "certificates"]

SECTION_HEADINGS: dict[str, list[str]] = {
    "skills": [
        "skills",
        "technical skills",
        "technical stack",
        "技能",
        "技能栏",
        "专业技能",
        "技术栈",
    ],
    "education": [
        "education",
        "academic background",
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
        "项目",
        "项目经历",
        "课程项目",
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
    "Python",
    "C++",
    "C",
    "FastAPI",
    "Flask",
    "Django",
    "Streamlit",
    "Pydantic",
    "LangGraph",
    "LangChain",
    "OpenAI API",
    "OpenAI",
    "LLM",
    "RAG",
    "MCP",
    "Ollama",
    "SQL",
    "SQLite",
    "PostgreSQL",
    "Redis",
    "Docker",
    "Git",
    "REST API",
    "pytest",
    "React",
    "TypeScript",
    "JavaScript",
    "HTML",
    "CSS",
    "Pandas",
    "NumPy",
    "PyTorch",
    "TensorFlow",
    "Transformers",
    "HuggingFace",
    "scikit-learn",
    "Librosa",
    "OpenCV",
    "CUDA",
    "Deep Learning",
    "Machine Learning",
    "STM32",
    "USART",
    "UART",
    "GPIO",
    "FreeRTOS",
    "RTOS",
    "I2C",
    "SPI",
    "CAN",
    "DMA",
    "ADC",
    "PWM",
    "Keil",
    "CubeMX",
    "机器学习",
    "数据分析",
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
    "公司",
    "实习",
    "科研",
    "助教",
    "实验室",
    "负责",
]

DEGREE_KEYWORDS = [
    "Bachelor",
    "B.S.",
    "BS",
    "BEng",
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
    "latency",
    "throughput",
    "dataset",
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
]

METRIC_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?\s?%|\d+\s?(?:ms|s|APIs?|tests?|users?|samples?|cases?)|[0-9]+k)",
    re.IGNORECASE,
)


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
        skill = _canonical_skill(token)
        if skill:
            found.append(skill)

    searchable_sections = [
        full_text,
        "\n".join(sections.get("projects", [])),
        "\n".join(sections.get("experience", [])),
    ]
    for text in searchable_sections:
        found.extend(_extract_known_skills(text))

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
        line for line in _all_lines(sections) if _contains_any(line, WORK_KEYWORDS)
    ]

    work_items: list[WorkExperience] = []
    for line in candidate_lines:
        if not experience_lines and not _contains_any(line, WORK_KEYWORDS):
            continue
        role, company = _extract_role_company(line)
        work_items.append(
            WorkExperience(
                company=company,
                role=role,
                description=line,
                technologies=_extract_known_skills(line),
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

    projects: list[ProjectExperience] = []
    for line in project_lines[:3]:
        name, description = _extract_project_name_description(line)
        raw_text = line
        projects.append(
            ProjectExperience(
                name=name or f"Project {len(projects) + 1}",
                description=description or raw_text,
                technologies=_extract_known_skills(raw_text),
                highlights=_extract_highlight_lines([raw_text]),
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
                ["certificate", "certification", "award", "honor", "CET", "证书", "奖项", "荣誉"],
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
        highlights = _extract_highlight_lines([line for line in full_text.splitlines()])
    return highlights[:5]


def _detect_heading(line: str) -> tuple[str | None, str | None]:
    normalized = _normalize_heading_text(line)
    prefix, inline_value = _split_heading_value(line)

    for key, headings in SECTION_HEADINGS.items():
        if normalized in {_normalize_heading_text(heading) for heading in headings}:
            return key, None
        if prefix and _normalize_heading_text(prefix) in {
            _normalize_heading_text(heading) for heading in headings
        }:
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
        for token in re.split(r"[,;；，/|、\n]", text)
        if token.strip()
    ]


def _canonical_skill(token: str) -> str | None:
    clean_token = token.strip()
    for skill in KNOWN_RESUME_SKILLS:
        if clean_token.lower() == skill.lower():
            return skill
    return None


def _extract_known_skills(text: str) -> list[str]:
    return [
        skill
        for skill in KNOWN_RESUME_SKILLS
        if _skill_in_text(skill, text)
    ]


def _skill_in_text(skill: str, text: str) -> bool:
    if not text:
        return False
    if re.search(r"[\u4e00-\u9fff]", skill):
        return skill in text
    escaped = re.escape(skill)
    return bool(re.search(rf"(?<![A-Za-z0-9+#.]){escaped}(?![A-Za-z0-9+#.])", text, re.IGNORECASE))


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
    in_match = re.search(r"\bin\s+([^,;；]+)", line, re.IGNORECASE)
    if in_match:
        return in_match.group(1).strip()
    degree_major_match = re.search(
        r"(?:B\.S\.|M\.S\.|BS|MS|MSc|BEng|Bachelor|Master|PhD)\s+([^,;；]+)",
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
    at_match = re.search(r"(.+?)\s+at\s+([^,;；]+)", line, re.IGNORECASE)
    if at_match:
        return at_match.group(1).strip(), at_match.group(2).strip()
    comma_parts = [part.strip() for part in re.split(r"[,，]", line) if part.strip()]
    if len(comma_parts) >= 2 and _contains_any(comma_parts[0], WORK_KEYWORDS):
        return comma_parts[0], comma_parts[1]
    return None, None


def _looks_like_project_line(line: str) -> bool:
    return _contains_any(
        line,
        ["project", "system", "platform", "application", "agent", "demo", "项目", "系统", "平台", "应用"],
    )


def _extract_project_name_description(line: str) -> tuple[str | None, str]:
    prefix, value = _split_heading_value(line)
    if prefix and _normalize_heading_text(prefix) in {"project", "projects", "项目", "项目经历"} and value:
        title, description = _split_title_description(value)
        return title, description
    title, description = _split_title_description(line)
    return title, description


def _split_title_description(text: str) -> tuple[str | None, str]:
    cleaned = text.strip()
    for separator in [". ", " - ", " — ", " – ", "，", "。"]:
        if separator in cleaned:
            title, rest = cleaned.split(separator, 1)
            if 3 <= len(title.strip()) <= 80:
                return title.strip(), rest.strip() or cleaned
    if len(cleaned) <= 80:
        return cleaned, cleaned
    return None, cleaned


def _extract_highlight_lines(lines: list[str]) -> list[str]:
    return _dedupe(
        [
            _clean_line(line)
            for line in lines
            if _clean_line(line)
            and (METRIC_PATTERN.search(line) or _contains_any(line, HIGHLIGHT_KEYWORDS))
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
