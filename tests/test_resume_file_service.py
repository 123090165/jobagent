from __future__ import annotations

import pytest

from app.services.resume_file_service import (
    ResumeFileParseError,
    extract_text_from_resume_file,
    get_resume_file_type,
    normalize_resume_filename,
)
from tests.test_mock_pipeline import SAMPLE_RESUME


def test_extract_text_from_txt_file() -> None:
    text = extract_text_from_resume_file("resume.txt", SAMPLE_RESUME.encode("utf-8"))

    assert text == SAMPLE_RESUME.strip()
    assert get_resume_file_type("resume.txt") == "txt"


def test_extract_text_from_md_file() -> None:
    markdown_resume = f"# Resume\n\n{SAMPLE_RESUME}"

    text = extract_text_from_resume_file("resume.md", markdown_resume.encode("utf-8"))

    assert text.startswith("# Resume")
    assert get_resume_file_type("resume.md") == "md"


def test_extract_text_normalizes_filename() -> None:
    filename = normalize_resume_filename(r"C:\fake\path\resume.TXT")
    text = extract_text_from_resume_file(filename, SAMPLE_RESUME.encode("utf-8"))

    assert filename == "resume.TXT"
    assert text == SAMPLE_RESUME.strip()


def test_extract_text_rejects_empty_file() -> None:
    with pytest.raises(ResumeFileParseError, match="resume file cannot be empty"):
        extract_text_from_resume_file("resume.txt", b"")

    with pytest.raises(ResumeFileParseError, match="resume file cannot be empty"):
        extract_text_from_resume_file("resume.md", b"   \n\t")


def test_extract_text_rejects_unsupported_extension() -> None:
    with pytest.raises(ResumeFileParseError, match="unsupported resume file type"):
        extract_text_from_resume_file("resume.pdf", b"fake pdf")


def test_extract_text_rejects_decode_failure() -> None:
    with pytest.raises(ResumeFileParseError, match="resume file must be UTF-8 text"):
        extract_text_from_resume_file("resume.txt", b"\xff\xfe\x00\x00")
