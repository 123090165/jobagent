from __future__ import annotations

import re

from app.schemas.job import JobAnalysis
from app.schemas.resume import EducationItem, ProjectExperience, ResumeProfile, WorkExperience
from app.services.resume_section_parser import (
    KNOWN_RESUME_SKILLS,
    extract_highlights_from_sections,
    parse_certificates_from_sections,
    parse_education_from_sections,
    parse_projects_from_sections,
    parse_skills_from_sections,
    parse_work_experience_from_sections,
    split_resume_sections,
)

KNOWN_SKILLS = [
    "Python",
    "FastAPI",
    "Pydantic",
    "LangGraph",
    "LangChain",
    "OpenAI",
    "LLM",
    "RAG",
    "MCP",
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
    "scikit-learn",
]
KNOWN_SKILLS = list(dict.fromkeys([*KNOWN_SKILLS, *KNOWN_RESUME_SKILLS]))


def _clean_lines(text: str) -> list[str]:
    return [line.strip(" -\t") for line in text.splitlines() if line.strip()]


def _extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for skill in KNOWN_SKILLS:
        if skill.lower() in lowered and skill not in found:
            found.append(skill)
    return found


def _split_clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。；;,，\n]", text) if part.strip()]


def _extract_preferred_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        if "plus" in line.lower() or "preferred" in line.lower() or "加分" in line:
            skills.extend(_extract_skills(line))
    return _dedupe(skills)


def _extract_required_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        lowered = line.lower()
        if any(token in lowered for token in ["require", "must", "responsib", "职责", "要求"]):
            skills.extend(_extract_skills(line))
    return _dedupe(skills)


def _first_reasonable_title(lines: list[str], fallback: str) -> str:
    for line in lines:
        if len(line) <= 80 and not any(token in line.lower() for token in ["职责", "要求", "responsib", "require"]):
            return line
    return fallback


def mock_resume_parse(resume_text: str) -> ResumeProfile:
    text = resume_text.strip()
    if not text:
        raise ValueError("resume_text cannot be empty")

    sections = split_resume_sections(text)
    flattened_text = "\n".join(sum(sections.values(), [])) if sections else text
    skills = parse_skills_from_sections(sections, flattened_text)
    projects = parse_projects_from_sections(sections)
    work_experiences = parse_work_experience_from_sections(sections)
    education = parse_education_from_sections(sections)
    certificates = parse_certificates_from_sections(sections)
    highlights = extract_highlights_from_sections(sections, flattened_text)

    if not skills:
        skills = _extract_skills(text)
    if not projects:
        project_text = _clean_lines(text)[0] if _clean_lines(text) else text[:120]
        projects = [
            ProjectExperience(
                name="General project",
                description=project_text,
                technologies=skills[:5],
                highlights=highlights[:3],
                raw_text=project_text,
            )
        ]
    if not education and any(token in text.lower() for token in ["university", "college", "b.s.", "m.s."]):
        education = [EducationItem(raw_text=text[:120])]
    if not work_experiences and any(token in text.lower() for token in ["intern", "assistant", "engineer"]):
        work_experiences = [
            WorkExperience(
                role=None,
                company=None,
                description=text[:160],
                technologies=skills[:5],
                raw_text=text[:160],
            )
        ]

    missing_info: list[str] = []
    if not skills:
        missing_info.append("skills")
    if not work_experiences:
        missing_info.append("work experience")
    if not highlights:
        missing_info.append("measurable outcomes")

    return ResumeProfile(
        raw_text=text,
        name=None,
        skills=skills,
        projects=projects,
        work_experiences=work_experiences,
        education=education,
        certificates=certificates,
        highlights=highlights,
        missing_info=missing_info,
    )


def mock_jd_analysis(jd_text: str) -> JobAnalysis:
    text = jd_text.strip()
    if not text:
        raise ValueError("jd_text cannot be empty")

    lines = _clean_lines(text)
    required_skills = _extract_required_skills(lines)
    preferred_skills = _extract_preferred_skills(lines)
    all_skills = _dedupe([*required_skills, *preferred_skills, *_extract_skills(text)])
    if not required_skills:
        required_skills = all_skills[:5]
    if not preferred_skills:
        preferred_skills = [skill for skill in all_skills if skill not in required_skills][:5]

    clauses = _split_clauses(text)
    responsibilities = [clause for clause in clauses if any(token in clause.lower() for token in ["负责", "design", "build", "develop", "maintain"])]
    experience_requirements = [clause for clause in clauses if "year" in clause.lower() or "经验" in clause]
    education_requirements = [clause for clause in clauses if "degree" in clause.lower() or "本科" in clause or "学历" in clause]
    soft_skills = [clause for clause in clauses if any(token in clause.lower() for token in ["communication", "collabor", "沟通", "协作"])]

    job_category = (
        "AI / LLM Application"
        if any(skill in all_skills for skill in ["LLM", "RAG", "OpenAI", "LangGraph"])
        else "Software Engineering"
    )
    return JobAnalysis(
        raw_jd=text,
        job_title=_first_reasonable_title(lines, "Target role"),
        responsibilities=responsibilities,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        experience_requirements=experience_requirements,
        education_requirements=education_requirements,
        soft_skills=soft_skills,
        implicit_requirements=["Explain project evidence clearly."],
        keywords=all_skills,
        job_category=job_category,
    )


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
