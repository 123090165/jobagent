from __future__ import annotations

import os
from pathlib import Path

from app.services.errors import JobAgentError


SUPPORTED_RESUME_FILE_TYPES = {
    ".txt": "txt",
    ".md": "md",
}
DEFAULT_MAX_RESUME_FILE_BYTES = 1 * 1024 * 1024
MAX_RESUME_FILE_BYTES_ENV = "JOBAGENT_MAX_RESUME_FILE_BYTES"


class ResumeFileParseError(JobAgentError):
    """Raised when an uploaded resume file cannot be converted to text."""


def normalize_resume_filename(filename: str | None) -> str:
    normalized = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not normalized:
        raise ResumeFileParseError("filename is required", "resume_filename_required")
    return normalized


def get_resume_file_type(filename: str | None) -> str:
    normalized = normalize_resume_filename(filename)
    extension = Path(normalized).suffix.lower()
    if extension not in SUPPORTED_RESUME_FILE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_RESUME_FILE_TYPES))
        file_type = extension or "missing extension"
        raise ResumeFileParseError(
            f"unsupported resume file type: {file_type}. supported types: {supported}",
            "resume_file_type_unsupported",
        )
    return SUPPORTED_RESUME_FILE_TYPES[extension]


def get_max_resume_file_bytes() -> int:
    raw_limit = os.getenv(MAX_RESUME_FILE_BYTES_ENV)
    if raw_limit is None or not raw_limit.strip():
        return DEFAULT_MAX_RESUME_FILE_BYTES

    try:
        max_bytes = int(raw_limit)
    except ValueError as exc:
        raise ResumeFileParseError(
            f"{MAX_RESUME_FILE_BYTES_ENV} must be a positive integer",
            "resume_file_size_limit_invalid",
        ) from exc

    if max_bytes <= 0:
        raise ResumeFileParseError(
            f"{MAX_RESUME_FILE_BYTES_ENV} must be a positive integer",
            "resume_file_size_limit_invalid",
        )
    return max_bytes


def validate_resume_file_size(content: bytes) -> None:
    if len(content) > get_max_resume_file_bytes():
        raise ResumeFileParseError("resume file is too large", "resume_file_too_large")


def extract_text_from_resume_file(filename: str | None, content: bytes) -> str:
    """Validate a supported resume file and return its UTF-8 text content."""
    get_resume_file_type(filename)
    validate_resume_file_size(content)
    if not content:
        raise ResumeFileParseError("resume file cannot be empty", "resume_file_empty")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ResumeFileParseError(
            "resume file must be UTF-8 text",
            "resume_file_decode_failed",
        ) from exc

    extracted_text = text.strip()
    if not extracted_text:
        raise ResumeFileParseError("resume file cannot be empty", "resume_file_empty")
    return extracted_text
