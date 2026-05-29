from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import ResumeParseRequest
from app.schemas.resume import ResumeProfile
from app.services.mock_pipeline import mock_resume_parse

router = APIRouter(tags=["resume"])


@router.post("/resume/parse", response_model=ResumeProfile)
def parse_resume(request: ResumeParseRequest) -> ResumeProfile:
    resume_text = request.resume_text.strip()
    if not resume_text:
        raise HTTPException(status_code=400, detail="resume_text cannot be empty")
    return mock_resume_parse(resume_text)
