from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.agents.resume_parse_agent import parse_resume as parse_resume_with_agent
from app.schemas.api import ResumeFileParseResponse, ResumeParseRequest
from app.schemas.resume import ResumeProfile
from app.services.errors import JobAgentError
from app.services.resume_file_service import (
    extract_text_from_resume_file,
    get_resume_file_type,
    normalize_resume_filename,
)

router = APIRouter(tags=["resume"])


@router.post("/resume/parse", response_model=ResumeProfile)
def parse_resume(request: ResumeParseRequest) -> ResumeProfile:
    try:
        return parse_resume_with_agent(request.resume_text)
    except ValueError as exc:
        raise JobAgentError("resume_text cannot be empty", "resume_text_empty") from exc


@router.post("/resume/parse-file", response_model=ResumeFileParseResponse)
async def parse_resume_file(file: UploadFile = File(...)) -> ResumeFileParseResponse:
    try:
        filename = normalize_resume_filename(file.filename)
        content = await file.read()
        extracted_text = extract_text_from_resume_file(filename, content)
        file_type = get_resume_file_type(filename)
        resume_profile = parse_resume_with_agent(extracted_text)
    except JobAgentError:
        raise
    except ValueError as exc:
        raise JobAgentError(str(exc), "resume_parse_failed") from exc

    return ResumeFileParseResponse(
        filename=filename,
        file_type=file_type,
        extracted_text=extracted_text,
        resume_profile=resume_profile,
    )
