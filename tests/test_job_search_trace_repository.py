from __future__ import annotations

from app.repositories.job_search_repository import JobSearchRepository
from app.storage.database import get_connection, init_database


def test_job_search_trace_steps_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-trace.sqlite3"))
    repository = JobSearchRepository()

    with get_connection() as connection:
        init_database(connection)
        connection.execute(
            """
            INSERT INTO profile_sessions (
                session_id, status, created_at, updated_at, current_step
            ) VALUES ('session-1', 'active', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', 'job_search_ready')
            """
        )
        connection.execute(
            """
            INSERT INTO resume_documents (
                resume_document_id, session_id, source_type, filename, file_type, text, text_length, created_at, updated_at
            ) VALUES (
                'resume-1', 'session-1', 'text', NULL, NULL, 'resume text', 11,
                '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO parsed_resume_reviews (
                parsed_review_id, session_id, resume_document_id, basic_info_json, education_json, work_experience_json,
                projects_json, skills_json, target_signals_json, quality_warnings_json, missing_info_questions_json,
                raw_parser_output_json, created_at, updated_at
            ) VALUES (
                'review-1', 'session-1', 'resume-1', '{}', '[]', '[]',
                '[]', '{"items":[],"count":0}', '[]', '[]', '[]',
                NULL, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO profile_drafts (
                profile_draft_id, session_id, parsed_review_id, summary, target_roles_json, target_directions_json,
                core_skills_json, supporting_skills_json, search_keywords_json, preferred_locations_json,
                work_arrangements_json, strengths_json, risks_json, missing_info_questions_json, created_at, updated_at
            ) VALUES (
                'draft-1', 'session-1', 'review-1', 'summary', '[]', '[]',
                '[]', '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO confirmed_profiles (
                confirmed_profile_id, session_id, resume_document_id, parsed_review_id, profile_draft_id,
                summary, target_roles_json, target_directions_json, core_skills_json, supporting_skills_json,
                search_keywords_json, preferred_locations_json, work_arrangements_json, strengths_json, risks_json,
                missing_info_questions_json, created_at, updated_at
            ) VALUES (
                'confirmed-1', 'session-1', 'resume-1', 'review-1', 'draft-1',
                'summary', '[]', '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]',
                '[]', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
            )
            """
        )
        connection.commit()

    run = repository.create_pending(
        session_id="session-1",
        confirmed_profile_id="confirmed-1",
        query="backend engineer python",
        locations=["Remote"],
        target_roles=["Backend Engineer"],
        keywords=["Python", "FastAPI"],
        search_mode="live_search",
        llm_enabled=True,
        search_provider="mock",
    )

    step = repository.create_trace_step(
        job_search_run_id=run.job_search_run_id,
        step_index=1,
        name="Search planning",
    )
    repository.mark_trace_step_running(
        step.step_id,
        mode="llm",
        summary="Planning search.",
        guardrails=["Do not invent experience."],
    )
    repository.complete_trace_step(
        step.step_id,
        mode="fallback",
        summary="Used fallback plan.",
        fallback_reason="LLMServiceError",
        guardrails=["Do not invent experience."],
        quality_warnings=["Planner fell back."],
    )

    steps = repository.list_trace_steps(run.job_search_run_id)

    assert len(steps) == 1
    assert steps[0].status == "completed"
    assert steps[0].mode == "fallback"
    assert steps[0].fallback_reason == "LLMServiceError"
    assert steps[0].duration_ms is not None
