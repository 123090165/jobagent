from __future__ import annotations

from app.application.profile_session_usecases import get_profile_session
from app.application.resume_intake_usecases import get_resume_document
from app.repositories.parsed_resume_review_repository import (
    ParsedResumeReviewRepository,
    parsed_resume_review_repository,
)
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.repositories.resume_document_repository import (
    ResumeDocumentRepository,
    resume_document_repository,
)
from app.schemas.parsed_resume_review import (
    ParsedResumeReview,
    ParsedResumeReviewResponse,
)
from app.services.errors import JobAgentError
from app.services.resume_profile_review_service import build_resume_profile_review


def parse_resume_for_review(
    session_id: str,
    *,
    regenerate: bool = False,
    session_repository: ProfileSessionRepository = profile_session_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
    parsed_review_repository: ParsedResumeReviewRepository = parsed_resume_review_repository,
) -> ParsedResumeReviewResponse:
    session = get_profile_session(session_id, repository=session_repository)
    if session.resume_document_id is None:
        raise JobAgentError(
            message="Resume review requires an existing resume document.",
            error_code="invalid_profile_session_state",
            status_code=409,
        )

    resume_document = get_resume_document(
        session_id,
        session_repository=session_repository,
        resume_repository=resume_repository,
    )

    if not regenerate:
        if session.parsed_review_id:
            existing = parsed_review_repository.get(session.parsed_review_id)
            if existing is not None and existing.resume_document_id == resume_document.resume_document_id:
                return ParsedResumeReviewResponse(
                    parsed_review=existing,
                    profile_session=session,
                )
        existing_for_resume = parsed_review_repository.get_current_for_session(
            session_id=session.session_id,
            resume_document_id=resume_document.resume_document_id,
        )
        if existing_for_resume is not None:
            updated_session = session_repository.attach_parsed_review(
                session_id=session.session_id,
                parsed_review_id=existing_for_resume.parsed_review_id,
            )
            return ParsedResumeReviewResponse(
                parsed_review=existing_for_resume,
                profile_session=updated_session or session,
            )

    review_result = build_resume_profile_review(resume_document.text)
    parsed_review = parsed_review_repository.create(
        session_id=session.session_id,
        resume_document_id=resume_document.resume_document_id,
        basic_info={
            "name": review_result.parsed_profile.name,
            "highlights": review_result.parsed_profile.highlights,
            "certificates": review_result.parsed_profile.certificates,
        },
        education=[
            item.model_dump(mode="json") for item in review_result.parsed_profile.education
        ],
        work_experience=[
            item.model_dump(mode="json")
            for item in review_result.parsed_profile.work_experiences
        ],
        projects=[
            item.model_dump(mode="json") for item in review_result.parsed_profile.projects
        ],
        skills={
            "items": review_result.parsed_profile.skills,
            "count": len(review_result.parsed_profile.skills),
        },
        target_signals=_build_target_signals(review_result.parsed_profile.skills),
        quality_warnings=review_result.quality_warnings,
        missing_info_questions=review_result.missing_info_questions,
        raw_parser_output=review_result.parsed_profile.model_dump(mode="json"),
    )
    updated_session = session_repository.attach_parsed_review(
        session_id=session.session_id,
        parsed_review_id=parsed_review.parsed_review_id,
    )
    return ParsedResumeReviewResponse(
        parsed_review=parsed_review,
        profile_session=updated_session or session,
    )


def get_parsed_resume_review(
    session_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    parsed_review_repository: ParsedResumeReviewRepository = parsed_resume_review_repository,
) -> ParsedResumeReviewResponse:
    session = get_profile_session(session_id, repository=session_repository)
    if session.parsed_review_id is None:
        raise JobAgentError(
            message="Parsed resume review not found for this session.",
            error_code="parsed_review_not_found",
            status_code=404,
        )
    parsed_review = parsed_review_repository.get(session.parsed_review_id)
    if parsed_review is None:
        raise JobAgentError(
            message="Parsed resume review not found for this session.",
            error_code="parsed_review_not_found",
            status_code=404,
        )
    return ParsedResumeReviewResponse(
        parsed_review=parsed_review,
        profile_session=session,
    )


def _build_target_signals(skills: list[str]) -> list[str]:
    lowered = " ".join(skills).lower()
    signals: list[str] = []
    if any(token in lowered for token in ["python", "fastapi", "api", "sql"]):
        signals.append("Backend engineering signal")
    if any(token in lowered for token in ["llm", "langgraph", "langchain", "agent"]):
        signals.append("AI application signal")
    if any(token in lowered for token in ["embedded", "stm32", "c++", "rtos"]):
        signals.append("Embedded systems signal")
    if not signals and skills:
        signals.append("Technical skill signal detected")
    return signals
