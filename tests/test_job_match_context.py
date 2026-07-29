from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job import JDRequirement, JobAnalysis
from app.services.job_candidate_scoring import (
    JobMatchContext,
    build_final_candidate_scorecard,
)
from app.services.job_search_execution.result_builder import _match_candidates
from app.services.job_search_planner import JobSearchPlan, SearchConstraint
from app.services.job_search_providers.base import RawJobCandidate


def _profile() -> ConfirmedProfile:
    now = datetime.now(timezone.utc)
    return ConfirmedProfile(
        confirmed_profile_id="profile-1",
        session_id="session-1",
        resume_document_id="resume-1",
        parsed_review_id="review-1",
        profile_draft_id="draft-1",
        summary="Backend developer",
        target_roles=["Backend Engineer"],
        core_skills=["Python"],
        created_at=now,
        updated_at=now,
    )


def _plan(*, internship_only: bool = False) -> JobSearchPlan:
    constraints = []
    if internship_only:
        constraints.append(
            SearchConstraint(
                kind="employment_type",
                operator="required",
                values=["internship"],
                source_text="Internship only",
            )
        )
    return JobSearchPlan(
        target_roles=["Backend Engineer"],
        ranking_policy="Prefer confirmed profile evidence.",
        structured_constraints=constraints,
        mode="deterministic",
    )


def _candidate(description: str) -> RawJobCandidate:
    return RawJobCandidate(
        title="Backend Engineer",
        company="Example",
        location="Remote",
        source_url="https://example.com/job",
        source_provider="test",
        snippet="Backend role",
        raw_description=description,
    )


def test_final_scorecard_distinguishes_supported_and_unknown_requirements() -> None:
    raw_jd = "Python is required. Rust is required. Three years of experience is required."
    analysis = JobAnalysis(
        raw_jd=raw_jd,
        requirements=[
            JDRequirement(
                category="skill",
                name="Python",
                necessity="required",
                evidence_quote="Python is required.",
                confidence=0.95,
            ),
            JDRequirement(
                category="skill",
                name="Rust",
                necessity="required",
                evidence_quote="Rust is required.",
                confidence=0.95,
            ),
            JDRequirement(
                category="experience",
                name="Three years of experience",
                necessity="required",
                evidence_quote="Three years of experience is required.",
                confidence=0.95,
            ),
        ],
    )
    candidate = _candidate(raw_jd)

    scorecard = build_final_candidate_scorecard(
        0,
        JobMatchContext(
            confirmed_profile=_profile(),
            search_plan=_plan(),
            candidate=candidate,
            analysis=analysis,
        ),
    )

    assert scorecard.score_breakdown["skill_evidence"] == 5
    assert scorecard.match_reasons[0] == "Profile evidence supports required skills: Python."
    assert any("Rust" in item for item in scorecard.unknowns)
    assert any("experience" in item for item in scorecard.unknowns)
    assert "Python is required." in scorecard.evidence_quotes
    assert scorecard.confidence_label in {"weak", "limited"}


def test_full_jd_can_reject_candidate_after_recall() -> None:
    candidate = _candidate("")
    analysis = JobAnalysis(
        raw_jd="This is a full-time permanent position.",
        job_title="Backend Engineer",
    )

    matched = _match_candidates(
        _profile(),
        _plan(internship_only=True),
        [
            {
                "candidate": candidate,
                "analysis": analysis,
                "analysis_mode": "deterministic",
                "scorecard": None,
            }
        ],
    )

    assert matched == []
