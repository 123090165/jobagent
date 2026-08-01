from __future__ import annotations

from pathlib import Path

from app.storage.database import get_connection, init_database


def test_fresh_database_uses_current_schema_only(tmp_path: Path) -> None:
    database_path = tmp_path / "jobagent.sqlite3"
    with get_connection(database_path) as connection:
        init_database(connection)
        init_database(connection)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {
        "users",
        "profile_sessions",
        "resume_documents",
        "parsed_resume_reviews",
        "profile_drafts",
        "confirmed_profiles",
        "resume_profiles",
        "job_search_runs",
        "job_search_items",
        "saved_jobs",
        "job_applications",
        "application_events",
        "communication_drafts",
        "tailored_resume_versions",
        "chat_conversations",
        "chat_turns",
        "rag_index_outbox",
        "rag_resource_status",
    } <= tables
    assert {
        "schema_migrations",
        "resume_records",
        "job_postings",
        "match_reports",
        "project_challenges",
        "analysis_records",
        "resume_versions",
        "workflow_step_traces",
        "application_records",
        "confirmed_profile_records",
    }.isdisjoint(tables)
