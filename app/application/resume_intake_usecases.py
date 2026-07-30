"""接收简历文本或文件，创建解析结果，并推进 ProfileSession 到待审阅阶段。"""

from __future__ import annotations

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
from app.services.resume_file_service import (
    ResumeFileParseError,
    extract_text_from_resume_file,
    get_resume_file_type,
    normalize_resume_filename,
)
from app.storage.database import LOCAL_USER_ID

MAX_RESUME_TEXT_LENGTH = 100_000
def submit_resume_text(
    session_id: str,
    text: str,
    *,
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
) -> ResumeIntakeResponse:
    """保存粘贴文本，并使该 session 现有的下游画像和搜索引用失效。"""
    session = get_profile_session(session_id, repository=session_repository, user_id=user_id)
    _validate_resume_text(text)
    document = resume_repository.create(
        session_id=session.session_id,
        source_type="text",
        text=text,
        user_id=user_id or LOCAL_USER_ID,
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
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
) -> ResumeIntakeResponse:
    """完成文件格式与资源限制检查后，进入和文本录入相同的持久化链路。"""
    session = get_profile_session(session_id, repository=session_repository, user_id=user_id)
    filename = normalize_resume_filename(upload_file.filename)
    raw_bytes = await upload_file.read()
    try:
        text = extract_text_from_resume_file(filename, raw_bytes)
    except ResumeFileParseError as exc:
        if exc.error_code in {"resume_file_type_unsupported", "resume_file_decode_failed"}:
            raise JobAgentError(
                message=exc.message,
                error_code="resume_file_unsupported_type",
                status_code=exc.status_code,
            ) from exc
        raise
    _validate_resume_text(text, empty_error_code="resume_file_empty", empty_message="Resume file is empty.")
    document = resume_repository.create(
        session_id=session.session_id,
        source_type="file",
        filename=filename,
        file_type=get_resume_file_type(filename),
        text=text,
        user_id=user_id or LOCAL_USER_ID,
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
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
) -> ResumeDocument:
    """只返回 session 当前指向的简历，避免读取已被替换的历史版本。"""
    session = get_profile_session(session_id, repository=session_repository, user_id=user_id)
    if session.resume_document_id is None:
        raise JobAgentError(
            message="Resume document not found for this session.",
            error_code="resume_document_not_found",
            status_code=404,
        )
    document = resume_repository.get(session.resume_document_id, user_id=user_id)
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
