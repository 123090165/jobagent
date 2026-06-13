from __future__ import annotations

from app.services.mock_pipeline import mock_resume_parse
from app.services.resume_section_parser import (
    KNOWN_RESUME_SKILLS,
    extract_highlights_from_sections,
    parse_education_from_sections,
    parse_projects_from_sections,
    parse_skills_from_sections,
    parse_work_experience_from_sections,
    split_resume_sections,
)
from app.services.resume_skill_lexicon import extract_resume_skills


def test_split_resume_sections_detects_english_and_chinese_headings() -> None:
    sections = split_resume_sections(
        """
Technical Skills: Python, FastAPI
教育经历：
B.S. in Electrical Engineering, CUHKSZ
项目经历：
STM32 智能小车控制系统
"""
    )

    assert sections["skills"] == ["Python, FastAPI"]
    assert "B.S. in Electrical Engineering, CUHKSZ" in sections["education"]
    assert "STM32 智能小车控制系统" in sections["projects"]


def test_skills_section_extracts_backend_and_embedded_skills() -> None:
    sections = split_resume_sections(
        """
Technical Skills: Python, FastAPI, LangGraph, Docker, PostgreSQL
Embedded: STM32 / USART / GPIO / FreeRTOS
"""
    )

    skills = parse_skills_from_sections(sections, "\n".join(sum(sections.values(), [])))

    assert "Python" in skills
    assert "FastAPI" in skills
    assert "LangGraph" in skills
    assert "STM32" in skills
    assert "USART" in skills
    assert "GPIO" in skills


def test_english_research_experience_becomes_work_experience() -> None:
    sections = split_resume_sections(
        """
Experience
Research Assistant, CUHKSZ AI Lab
- Built a PyTorch audio classification baseline with 95% validation accuracy.
"""
    )

    work = parse_work_experience_from_sections(sections)

    assert work
    assert work[0].role == "Research Assistant"
    assert work[0].company == "CUHKSZ AI Lab"
    assert any("PyTorch" in item.technologies for item in work)


def test_education_line_extracts_school_degree_and_major() -> None:
    sections = split_resume_sections(
        """
Education:
B.S. in Electrical Engineering, CUHKSZ
M.S. Data Science, City University
"""
    )

    education = parse_education_from_sections(sections)

    assert education[0].degree == "B.S."
    assert education[0].major == "Electrical Engineering"
    assert education[0].school == "CUHKSZ"
    assert education[1].major == "Data Science"
    assert education[1].school == "City University"


def test_project_title_extraction_uses_real_project_names() -> None:
    sections = split_resume_sections(
        """
Projects:
DeepJSCC Speech Communication Project
JobAgent - AI job analysis workflow using FastAPI and Streamlit.
"""
    )

    projects = parse_projects_from_sections(sections)

    assert projects[0].name == "DeepJSCC Speech Communication Project"
    assert projects[1].name == "JobAgent"
    assert not all(project.name.startswith("Project ") for project in projects if project.name)


def test_metric_highlight_extraction_catches_common_outcomes() -> None:
    sections = split_resume_sections(
        """
Projects:
JobAgent - delivered 20 APIs, passed 300 tests, and reached 95% accuracy.
"""
    )

    highlights = extract_highlights_from_sections(
        sections,
        "\n".join(sum(sections.values(), [])),
    )

    assert any("95% accuracy" in item for item in highlights)
    assert any("20 APIs" in item for item in highlights)
    assert any("300 tests" in item for item in highlights)


def test_unstructured_resume_still_returns_profile() -> None:
    profile = mock_resume_parse("I know Python and want an AI job.")

    assert profile.raw_text
    assert "Python" in profile.skills
    assert profile.projects


def test_parser_extracts_ai_health_audio_and_business_terms() -> None:
    sections = split_resume_sections(
        """
Technical Skills: Python, PyTorch, Librosa, MFCC, STFT, CNN, RNN, Wind, CRM
Projects:
Physiological Signal Processing for wearable health monitoring
- Built a multimodal biosignal pipeline using PPG, ECG, ACC, denoising, and feature extraction.
"""
    )

    skills = parse_skills_from_sections(sections, "\n".join(sum(sections.values(), [])))

    assert {"PPG", "ECG", "ACC"} <= set(skills)
    assert {"MFCC", "STFT", "CNN", "RNN"} <= set(skills)
    assert {"Wind", "CRM"} <= set(skills)


def test_short_token_skills_do_not_false_positive_on_plain_words() -> None:
    text = (
        "We can support growth and research goals. "
        "The team will go deeper after the review."
    )

    skills = extract_resume_skills(text)

    assert "C" not in skills
    assert "Go" not in skills
    assert "CAN" not in skills


def test_can_bus_and_c_language_are_detected_in_context() -> None:
    text = "Technical Skills: C, CAN bus, STM32, UART"

    skills = extract_resume_skills(text)

    assert "C" in skills
    assert "CAN" in skills
    assert "STM32" in skills
    assert KNOWN_RESUME_SKILLS
