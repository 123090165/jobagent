from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from app.application.profile_session_usecases import get_profile_session
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.repositories.resume_document_repository import (
    ResumeDocumentRepository,
    resume_document_repository,
)
from app.schemas.resume_document import ResumeDocument
from app.schemas.resume_intake import ResumeIntakeResponse
from app.services.errors import JobAgentError

MAX_RESUME_TEXT_LENGTH = 100_000
MAX_RESUME_FILE_SIZE_BYTES = 1_000_000
SUPPORTED_RESUME_FILE_TYPES = {".txt": "txt", ".md": "md"}


def submit_resume_text(
    session_id: str,
    text: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
) -> ResumeIntakeResponse:
    session = get_profile_session(session_id, repository=session_repository)
    _validate_resume_text(text)
    document = resume_repository.create(
        session_id=session.session_id,
        source_type="text",
        text=text,
    )
    updated_session = session_repository.attach_resume_document(
        session_id=session.session_id,
        resume_document_id=document.resume_document_id,
    )
    return ResumeIntakeResponse(
        resume_document=document,
        profile_session=updated_session or session,
    )


async def submit_resume_file(
    session_id: str,
    upload_file: UploadFile,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
) -> ResumeIntakeResponse:
    session = get_profile_session(session_id, repository=session_repository)
    filename = upload_file.filename or ""
    file_extension = Path(filename).suffix.lower()
    if file_extension not in SUPPORTED_RESUME_FILE_TYPES:
        raise JobAgentError(
            message="Only .txt and .md resume files are supported in v4.1.",
            error_code="resume_file_unsupported_type",
            status_code=400,
        )

    raw_bytes = await upload_file.read()
    if not raw_bytes:
        raise JobAgentError(
            message="Resume file is empty.",
            error_code="resume_file_empty",
            status_code=400,
        )
    if len(raw_bytes) > MAX_RESUME_FILE_SIZE_BYTES:
        raise JobAgentError(
            message="Resume file is too large.",
            error_code="resume_file_too_large",
            status_code=400,
        )

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JobAgentError(
            message="Resume file must be valid UTF-8 text.",
            error_code="resume_file_unsupported_type",
            status_code=400,
        ) from exc

    _validate_resume_text(text, empty_error_code="resume_file_empty", empty_message="Resume file is empty.")
    document = resume_repository.create(
        session_id=session.session_id,
        source_type="file",
        filename=filename,
        file_type=SUPPORTED_RESUME_FILE_TYPES[file_extension],
        text=text,
    )
    updated_session = session_repository.attach_resume_document(
        session_id=session.session_id,
        resume_document_id=document.resume_document_id,
    )
    return ResumeIntakeResponse(
        resume_document=document,
        profile_session=updated_session or session,
    )


def get_resume_document(
    session_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
) -> ResumeDocument:
    session = get_profile_session(session_id, repository=session_repository)
    if session.resume_document_id is None:
        raise JobAgentError(
            message="Resume document not found for this session.",
            error_code="resume_document_not_found",
            status_code=404,
        )
    document = resume_repository.get(session.resume_document_id)
    if document is None:
        raise JobAgentError(
            message="Resume document not found for this session.",
            error_code="resume_document_not_found",
            status_code=404,
        )
    return document


def _validate_resume_text(
    text: str,
    *,
    empty_error_code: str = "resume_empty",
    empty_message: str = "Resume text is empty.",
) -> None:
    if not text.strip():
        raise JobAgentError(
            message=empty_message,
            error_code=empty_error_code,
            status_code=400,
        )
    if len(text) > MAX_RESUME_TEXT_LENGTH:
        raise JobAgentError(
            message="Resume text is too long.",
            error_code="resume_text_too_long",
            status_code=400,
        )
