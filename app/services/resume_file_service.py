from __future__ import annotations

from pathlib import Path


SUPPORTED_RESUME_FILE_TYPES = {
    ".txt": "txt",
    ".md": "md",
}


class ResumeFileParseError(ValueError):
    """Raised when an uploaded resume file cannot be converted to text."""


def normalize_resume_filename(filename: str | None) -> str:
    normalized = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not normalized:
        raise ResumeFileParseError("filename is required")
    return normalized


def get_resume_file_type(filename: str | None) -> str:
    normalized = normalize_resume_filename(filename)
    extension = Path(normalized).suffix.lower()
    if extension not in SUPPORTED_RESUME_FILE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_RESUME_FILE_TYPES))
        file_type = extension or "missing extension"
        raise ResumeFileParseError(
            f"unsupported resume file type: {file_type}. supported types: {supported}"
        )
    return SUPPORTED_RESUME_FILE_TYPES[extension]


def extract_text_from_resume_file(filename: str | None, content: bytes) -> str:
    """Validate a supported resume file and return its UTF-8 text content."""
    get_resume_file_type(filename)
    if not content:
        raise ResumeFileParseError("resume file cannot be empty")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ResumeFileParseError("resume file must be UTF-8 text") from exc

    extracted_text = text.strip()
    if not extracted_text:
        raise ResumeFileParseError("resume file cannot be empty")
    return extracted_text
