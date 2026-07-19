from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_candidate_filter import filter_candidates
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate


def test_excluded_mission_role_adds_penalty_and_changes_ranking() -> None:
    profile = ConfirmedProfile.model_validate(
        {
            "confirmed_profile_id": "profile-1",
            "session_id": "session-1",
            "resume_document_id": "resume-1",
            "parsed_review_id": "review-1",
            "profile_draft_id": "draft-1",
            "summary": "Python backend and customer-facing implementation work.",
            "target_roles": ["Backend Engineer"],
            "target_directions": [],
            "core_skills": ["Python", "FastAPI"],
            "supporting_skills": [],
            "search_keywords": ["backend"],
            "preferred_locations": ["Remote"],
            "work_arrangements": ["Remote"],
            "strengths": [],
            "risks": [],
            "missing_info_questions": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )
    plan = JobSearchPlan(
        locations=["Remote"],
        target_roles=["Backend Engineer"],
        must_have_signals=["Python"],
        avoid_signals=["Sales Engineer"],
        ranking_policy="Prefer backend roles and exclude sales roles.",
        mode="deterministic",
    )
    candidates = [
        RawJobCandidate(
            title="Sales Engineer",
            company="A",
            location="Remote",
            source_url="https://example.com/sales",
            source_provider="test",
            snippet="Python FastAPI backend demos and customer sales work.",
            raw_description="Python FastAPI backend demos and customer sales work.",
        ),
        RawJobCandidate(
            title="Backend Engineer",
            company="B",
            location="Remote",
            source_url="https://example.com/backend",
            source_provider="test",
            snippet="Python FastAPI backend services.",
            raw_description="Python FastAPI backend services.",
        ),
    ]

    result = filter_candidates(profile, plan, candidates, use_llm=False, limit=2)
    scorecards = {item.candidate_index: item for item in result.scorecards}

    assert result.selected_indexes[0] == 1
    assert scorecards[0].score_breakdown["risk_penalty"] >= 6
    assert any("sales engineer" in risk.lower() for risk in scorecards[0].risks)
