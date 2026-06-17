from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DATABASE_PATH = Path("data/jobagent.sqlite3")


def get_database_path() -> Path:
    return Path(os.getenv("JOBAGENT_DB_PATH", str(DEFAULT_DATABASE_PATH)))


def get_connection(database_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(database_path) if database_path else get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS resume_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS job_postings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_jd TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            job_title TEXT,
            company TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS match_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_record_id INTEGER NOT NULL,
            job_posting_id INTEGER NOT NULL,
            report_json TEXT NOT NULL,
            overall_score REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resume_record_id) REFERENCES resume_records(id),
            FOREIGN KEY (job_posting_id) REFERENCES job_postings(id)
        );

        CREATE TABLE IF NOT EXISTS project_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_report_id INTEGER NOT NULL,
            challenge_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_report_id) REFERENCES match_reports(id)
        );

        CREATE TABLE IF NOT EXISTS analysis_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_record_id INTEGER NOT NULL,
            job_posting_id INTEGER NOT NULL,
            application_id INTEGER,
            match_report_id INTEGER NOT NULL,
            project_challenge_id INTEGER NOT NULL,
            optimization_json TEXT NOT NULL,
            markdown_report TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resume_record_id) REFERENCES resume_records(id),
            FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
            FOREIGN KEY (application_id) REFERENCES application_records(id),
            FOREIGN KEY (match_report_id) REFERENCES match_reports(id),
            FOREIGN KEY (project_challenge_id) REFERENCES project_challenges(id)
        );

        CREATE TABLE IF NOT EXISTS resume_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            base_resume_text TEXT NOT NULL,
            tailored_resume_text TEXT,
            target_job_posting_id INTEGER,
            source_analysis_record_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_job_posting_id) REFERENCES job_postings(id),
            FOREIGN KEY (source_analysis_record_id) REFERENCES analysis_records(id)
        );

        CREATE TABLE IF NOT EXISTS workflow_step_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_record_id INTEGER NOT NULL,
            workflow_run_id TEXT,
            step_index INTEGER NOT NULL,
            agent_name TEXT NOT NULL,
            status TEXT NOT NULL,
            mode TEXT NOT NULL,
            summary TEXT NOT NULL,
            duration_ms REAL,
            fallback_reason TEXT,
            guardrails_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_record_id) REFERENCES analysis_records(id)
        );

        CREATE TABLE IF NOT EXISTS application_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_posting_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'interested',
            notes TEXT,
            next_action TEXT,
            resume_version_id INTEGER,
            resume_version_label TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
            FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id)
        );

        CREATE TABLE IF NOT EXISTS confirmed_profile_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_record_id INTEGER,
            raw_resume_text TEXT NOT NULL,
            baseline_profile_json TEXT NOT NULL,
            confirmed_profile_json TEXT NOT NULL,
            user_edits_json TEXT NOT NULL,
            confirmation_summary_json TEXT NOT NULL,
            remaining_warnings_json TEXT NOT NULL,
            suggestion_decisions_json TEXT NOT NULL,
            missing_info_answers_json TEXT NOT NULL,
            confidence_label TEXT NOT NULL,
            target_roles_json TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resume_record_id) REFERENCES resume_records(id)
        );

        CREATE TABLE IF NOT EXISTS profile_sessions (
            session_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resume_document_id TEXT,
            parsed_review_id TEXT,
            profile_draft_id TEXT,
            confirmed_profile_id TEXT,
            current_step TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resume_documents (
            resume_document_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            filename TEXT,
            file_type TEXT,
            text TEXT NOT NULL,
            text_length INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS parsed_resume_reviews (
            parsed_review_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            resume_document_id TEXT NOT NULL,
            basic_info_json TEXT NOT NULL,
            education_json TEXT NOT NULL,
            work_experience_json TEXT NOT NULL,
            projects_json TEXT NOT NULL,
            skills_json TEXT NOT NULL,
            target_signals_json TEXT NOT NULL,
            quality_warnings_json TEXT NOT NULL,
            missing_info_questions_json TEXT NOT NULL,
            raw_parser_output_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (resume_document_id) REFERENCES resume_documents(resume_document_id)
        );

        CREATE TABLE IF NOT EXISTS profile_drafts (
            profile_draft_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            parsed_review_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            target_roles_json TEXT NOT NULL,
            target_directions_json TEXT NOT NULL,
            core_skills_json TEXT NOT NULL,
            supporting_skills_json TEXT NOT NULL,
            search_keywords_json TEXT NOT NULL,
            preferred_locations_json TEXT NOT NULL,
            work_arrangements_json TEXT NOT NULL,
            strengths_json TEXT NOT NULL,
            risks_json TEXT NOT NULL,
            missing_info_questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (parsed_review_id) REFERENCES parsed_resume_reviews(parsed_review_id)
        );

        CREATE TABLE IF NOT EXISTS confirmed_profiles (
            confirmed_profile_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            resume_document_id TEXT NOT NULL,
            parsed_review_id TEXT NOT NULL,
            profile_draft_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            target_roles_json TEXT NOT NULL,
            target_directions_json TEXT NOT NULL,
            core_skills_json TEXT NOT NULL,
            supporting_skills_json TEXT NOT NULL,
            search_keywords_json TEXT NOT NULL,
            preferred_locations_json TEXT NOT NULL,
            work_arrangements_json TEXT NOT NULL,
            strengths_json TEXT NOT NULL,
            risks_json TEXT NOT NULL,
            missing_info_questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (resume_document_id) REFERENCES resume_documents(resume_document_id),
            FOREIGN KEY (parsed_review_id) REFERENCES parsed_resume_reviews(parsed_review_id),
            FOREIGN KEY (profile_draft_id) REFERENCES profile_drafts(profile_draft_id)
        );

        CREATE TABLE IF NOT EXISTS job_search_runs (
            job_search_run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            confirmed_profile_id TEXT NOT NULL,
            query TEXT NOT NULL,
            locations_json TEXT NOT NULL,
            target_roles_json TEXT NOT NULL,
            keywords_json TEXT NOT NULL,
            search_mode TEXT NOT NULL DEFAULT 'local_mock',
            llm_enabled INTEGER NOT NULL DEFAULT 0,
            search_provider TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            results_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (confirmed_profile_id) REFERENCES confirmed_profiles(confirmed_profile_id)
        );

        CREATE TABLE IF NOT EXISTS job_search_trace_steps (
            step_id TEXT PRIMARY KEY,
            job_search_run_id TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            mode TEXT NOT NULL,
            summary TEXT NOT NULL,
            fallback_reason TEXT,
            guardrails_json TEXT NOT NULL,
            quality_warnings_json TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            duration_ms REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (job_search_run_id) REFERENCES job_search_runs(job_search_run_id)
        );
        """
    )
    _ensure_column(connection, "analysis_records", "application_id", "INTEGER")
    _ensure_column(connection, "application_records", "resume_version_id", "INTEGER")
    _ensure_column(connection, "workflow_step_traces", "workflow_run_id", "TEXT")
    _ensure_column(connection, "workflow_step_traces", "duration_ms", "REAL")
    _ensure_column(connection, "job_search_runs", "search_mode", "TEXT DEFAULT 'local_mock'")
    _ensure_column(connection, "job_search_runs", "llm_enabled", "INTEGER DEFAULT 0")
    _ensure_column(connection, "job_search_runs", "search_provider", "TEXT")
    _ensure_column(connection, "job_search_runs", "error_message", "TEXT")
    connection.commit()


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
