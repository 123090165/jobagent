from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DATABASE_PATH = Path("data/jobagent.sqlite3")
LOCAL_USER_ID = "local-user"
LOCAL_USERNAME = "local"


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
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_algorithm TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            disabled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            auth_session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

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
            user_id TEXT NOT NULL DEFAULT 'local-user',
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resume_document_id TEXT,
            parsed_review_id TEXT,
            profile_draft_id TEXT,
            confirmed_profile_id TEXT,
            current_step TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS resume_documents (
            resume_document_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local-user',
            source_type TEXT NOT NULL,
            filename TEXT,
            file_type TEXT,
            text TEXT NOT NULL,
            text_length INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS parsed_resume_reviews (
            parsed_review_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            resume_document_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local-user',
            basic_info_json TEXT NOT NULL,
            education_json TEXT NOT NULL,
            work_experience_json TEXT NOT NULL,
            projects_json TEXT NOT NULL,
            skills_json TEXT NOT NULL,
            target_signals_json TEXT NOT NULL,
            quality_warnings_json TEXT NOT NULL,
            missing_info_questions_json TEXT NOT NULL,
            raw_parser_output_json TEXT,
            analysis_mode TEXT NOT NULL DEFAULT 'deterministic',
            analysis_provider TEXT,
            analysis_warnings_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (resume_document_id) REFERENCES resume_documents(resume_document_id)
        );

        CREATE TABLE IF NOT EXISTS profile_drafts (
            profile_draft_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            parsed_review_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local-user',
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
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (parsed_review_id) REFERENCES parsed_resume_reviews(parsed_review_id)
        );

        CREATE TABLE IF NOT EXISTS confirmed_profiles (
            confirmed_profile_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            resume_document_id TEXT NOT NULL,
            parsed_review_id TEXT NOT NULL,
            profile_draft_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local-user',
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
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (resume_document_id) REFERENCES resume_documents(resume_document_id),
            FOREIGN KEY (parsed_review_id) REFERENCES parsed_resume_reviews(parsed_review_id),
            FOREIGN KEY (profile_draft_id) REFERENCES profile_drafts(profile_draft_id)
        );

        CREATE TABLE IF NOT EXISTS resume_profiles (
            resume_profile_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_session_id TEXT,
            source_confirmed_profile_id TEXT,
            name TEXT NOT NULL,
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
            profile_json TEXT NOT NULL,
            raw_resume_text TEXT,
            is_default INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (source_session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (source_confirmed_profile_id)
                REFERENCES confirmed_profiles(confirmed_profile_id)
        );

        CREATE TABLE IF NOT EXISTS job_search_runs (
            job_search_run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            confirmed_profile_id TEXT NOT NULL,
            resume_profile_id TEXT,
            user_id TEXT NOT NULL DEFAULT 'local-user',
            query TEXT NOT NULL,
            locations_json TEXT NOT NULL,
            target_roles_json TEXT NOT NULL,
            keywords_json TEXT NOT NULL,
            search_mode TEXT NOT NULL DEFAULT 'local_mock',
            llm_enabled INTEGER NOT NULL DEFAULT 0,
            search_provider TEXT,
            search_mission_id TEXT,
            search_mission_revision INTEGER,
            mission_constraints_json TEXT NOT NULL DEFAULT '[]',
            mission_excluded_roles_json TEXT NOT NULL DEFAULT '[]',
            mission_ranking_priorities_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            error_message TEXT,
            results_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (confirmed_profile_id) REFERENCES confirmed_profiles(confirmed_profile_id),
            FOREIGN KEY (resume_profile_id) REFERENCES resume_profiles(resume_profile_id)
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
            details_json TEXT NOT NULL DEFAULT '{}',
            started_at TEXT,
            completed_at TEXT,
            duration_ms REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (job_search_run_id) REFERENCES job_search_runs(job_search_run_id)
        );

        CREATE TABLE IF NOT EXISTS saved_jobs (
            saved_job_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_provider TEXT,
            source_url TEXT,
            normalized_source_key TEXT,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            salary TEXT,
            employment_type TEXT,
            raw_jd_text TEXT NOT NULL,
            structured_jd_json TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'saved',
            notes TEXT,
            first_seen_at TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS saved_job_analyses (
            saved_job_analysis_id TEXT PRIMARY KEY,
            saved_job_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            resume_profile_id TEXT,
            source_job_search_run_id TEXT,
            source_job_result_id TEXT,
            match_score INTEGER,
            confidence_label TEXT,
            recommendation TEXT,
            matched_strengths_json TEXT NOT NULL DEFAULT '[]',
            critical_gaps_json TEXT NOT NULL DEFAULT '[]',
            resume_actions_json TEXT NOT NULL DEFAULT '[]',
            interview_questions_json TEXT NOT NULL DEFAULT '[]',
            analysis_json TEXT NOT NULL,
            analysis_mode TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (saved_job_id) REFERENCES saved_jobs(saved_job_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (resume_profile_id) REFERENCES resume_profiles(resume_profile_id),
            FOREIGN KEY (source_job_search_run_id)
                REFERENCES job_search_runs(job_search_run_id)
        );

        CREATE TABLE IF NOT EXISTS saved_job_origins (
            saved_job_origin_id TEXT PRIMARY KEY,
            origin_key TEXT NOT NULL,
            user_id TEXT NOT NULL,
            saved_job_id TEXT NOT NULL,
            origin_type TEXT NOT NULL,
            resume_profile_id TEXT,
            job_search_run_id TEXT,
            job_search_result_id TEXT,
            saved_job_analysis_id TEXT,
            profile_label_snapshot TEXT,
            search_query_snapshot TEXT,
            source_provider TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (saved_job_id) REFERENCES saved_jobs(saved_job_id),
            FOREIGN KEY (resume_profile_id) REFERENCES resume_profiles(resume_profile_id),
            FOREIGN KEY (job_search_run_id) REFERENCES job_search_runs(job_search_run_id),
            FOREIGN KEY (saved_job_analysis_id) REFERENCES saved_job_analyses(saved_job_analysis_id),
            UNIQUE (user_id, saved_job_id, origin_key)
        );

        CREATE TABLE IF NOT EXISTS job_search_result_feedback (
            feedback_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_search_run_id TEXT NOT NULL,
            job_result_id TEXT NOT NULL,
            confirmed_profile_id TEXT NOT NULL,
            resume_profile_id TEXT,
            source_provider TEXT,
            feedback_type TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (job_search_run_id) REFERENCES job_search_runs(job_search_run_id),
            FOREIGN KEY (confirmed_profile_id) REFERENCES confirmed_profiles(confirmed_profile_id),
            FOREIGN KEY (resume_profile_id) REFERENCES resume_profiles(resume_profile_id),
            UNIQUE (user_id, job_search_run_id, job_result_id)
        );

        CREATE TABLE IF NOT EXISTS saved_job_status_events (
            saved_job_status_event_id TEXT PRIMARY KEY,
            saved_job_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            reason TEXT,
            changed_at TEXT NOT NULL,
            FOREIGN KEY (saved_job_id) REFERENCES saved_jobs(saved_job_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS job_briefs (
            job_brief_id TEXT PRIMARY KEY,
            saved_job_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            resume_profile_id TEXT,
            source_analysis_id TEXT,
            version INTEGER NOT NULL,
            content_json TEXT NOT NULL,
            analysis_mode TEXT NOT NULL,
            analysis_provider TEXT,
            fallback_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (saved_job_id) REFERENCES saved_jobs(saved_job_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (resume_profile_id) REFERENCES resume_profiles(resume_profile_id),
            FOREIGN KEY (source_analysis_id) REFERENCES saved_job_analyses(saved_job_analysis_id),
            UNIQUE (user_id, saved_job_id, version)
        );

        CREATE TABLE IF NOT EXISTS interview_preparations (
            preparation_id TEXT PRIMARY KEY,
            saved_job_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            resume_profile_id TEXT,
            source_analysis_id TEXT,
            status TEXT NOT NULL,
            skill_gaps_json TEXT NOT NULL DEFAULT '[]',
            questions_json TEXT NOT NULL DEFAULT '[]',
            answers_json TEXT NOT NULL DEFAULT '[]',
            learning_resources_json TEXT NOT NULL DEFAULT '[]',
            recommendations_json TEXT NOT NULL DEFAULT '[]',
            analysis_mode TEXT NOT NULL,
            analysis_provider TEXT,
            fallback_reason TEXT,
            question_generation_json TEXT,
            recommendation_generation_json TEXT,
            resource_mode TEXT NOT NULL DEFAULT 'none',
            resource_warning TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (saved_job_id) REFERENCES saved_jobs(saved_job_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (resume_profile_id) REFERENCES resume_profiles(resume_profile_id),
            FOREIGN KEY (source_analysis_id) REFERENCES saved_job_analyses(saved_job_analysis_id),
            UNIQUE (user_id, saved_job_id)
        );

        CREATE TABLE IF NOT EXISTS learning_topics (
            topic_id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL UNIQUE,
            aliases_json TEXT NOT NULL DEFAULT '[]',
            category TEXT NOT NULL DEFAULT 'technology'
        );

        CREATE TABLE IF NOT EXISTS learning_resources (
            resource_id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'review',
            reason TEXT NOT NULL,
            quality_tier INTEGER NOT NULL DEFAULT 1,
            is_curated INTEGER NOT NULL DEFAULT 1,
            last_verified_at TEXT,
            FOREIGN KEY (topic_id) REFERENCES learning_topics(topic_id)
        );

        CREATE TABLE IF NOT EXISTS search_missions (
            search_mission_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            confirmed_profile_id TEXT NOT NULL,
            status TEXT NOT NULL,
            input_json TEXT NOT NULL,
            mission_json TEXT NOT NULL,
            analysis_mode TEXT NOT NULL,
            analysis_provider TEXT,
            fallback_reason TEXT,
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            confirmed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (session_id) REFERENCES profile_sessions(session_id),
            FOREIGN KEY (confirmed_profile_id) REFERENCES confirmed_profiles(confirmed_profile_id),
            UNIQUE (user_id, session_id)
        );
        """
    )
    _ensure_local_user(connection)
    _ensure_column(connection, "analysis_records", "application_id", "INTEGER")
    _ensure_column(connection, "application_records", "resume_version_id", "INTEGER")
    _ensure_column(connection, "workflow_step_traces", "workflow_run_id", "TEXT")
    _ensure_column(connection, "workflow_step_traces", "duration_ms", "REAL")
    _ensure_column(connection, "job_search_runs", "search_mode", "TEXT DEFAULT 'local_mock'")
    _ensure_column(connection, "job_search_runs", "llm_enabled", "INTEGER DEFAULT 0")
    _ensure_column(connection, "job_search_runs", "search_provider", "TEXT")
    _ensure_column(connection, "job_search_runs", "resume_profile_id", "TEXT")
    _ensure_column(connection, "job_search_runs", "error_message", "TEXT")
    _ensure_column(connection, "job_search_runs", "search_mission_id", "TEXT")
    _ensure_column(connection, "job_search_runs", "search_mission_revision", "INTEGER")
    _ensure_column(connection, "job_search_runs", "mission_constraints_json", "TEXT DEFAULT '[]'")
    _ensure_column(connection, "job_search_runs", "mission_excluded_roles_json", "TEXT DEFAULT '[]'")
    _ensure_column(connection, "job_search_runs", "mission_ranking_priorities_json", "TEXT DEFAULT '[]'")
    _ensure_column(connection, "job_search_trace_steps", "details_json", "TEXT DEFAULT '{}'")
    _ensure_column(connection, "parsed_resume_reviews", "analysis_mode", "TEXT DEFAULT 'deterministic'")
    _ensure_column(connection, "parsed_resume_reviews", "analysis_provider", "TEXT")
    _ensure_column(connection, "parsed_resume_reviews", "analysis_warnings_json", "TEXT DEFAULT '[]'")
    _ensure_column(connection, "interview_preparations", "question_generation_json", "TEXT")
    _ensure_column(connection, "interview_preparations", "recommendation_generation_json", "TEXT")
    _ensure_user_columns(connection)
    _backfill_user_ownership(connection)
    _backfill_saved_job_status_events(connection)
    _ensure_indexes(connection)
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (version, name)
        VALUES (1, 'auth_and_user_libraries')
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (2, 'job_preparation_and_learning_catalog')"
    )
    lineage_migration = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version = 3"
    ).fetchone()
    if lineage_migration is None:
        _backfill_saved_job_lineage(connection)
        connection.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (3, 'saved_job_origin_lineage')"
        )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (4, 'preparation_generation_stages')"
    )
    _seed_learning_catalog(connection)
    connection.commit()


def _seed_learning_catalog(connection: sqlite3.Connection) -> None:
    topics = [
        ("python", "Python", '["python3"]'),
        ("sql", "SQL", '["relational database", "databases"]'),
        ("linux", "Linux", '["unix", "shell"]'),
        ("git", "Git", '["version control"]'),
        ("docker", "Docker", '["containers", "containerization"]'),
        ("kubernetes", "Kubernetes", '["k8s"]'),
        ("typescript", "TypeScript", '["ts"]'),
        ("microsoft-office", "Microsoft Office", '["excel", "word", "powerpoint", "microsoft 365"]'),
        ("physiological-signals", "Physiological signal processing", '["biosignal", "ppg", "ecg", "acc", "multimodal physiological signal"]'),
        ("ppg-blood-pressure", "PPG blood pressure estimation", '["blood pressure estimation from ppg", "cuffless blood pressure", "pulse transit time", "ptt"]'),
        ("mlflow", "MLflow", '["model iteration", "experiment tracking", "mlops"]'),
    ]
    connection.executemany(
        "INSERT OR IGNORE INTO learning_topics (topic_id, canonical_name, aliases_json) VALUES (?, ?, ?)",
        topics,
    )
    resources = [
        ("python-tutorial", "python", "The Python Tutorial", "https://docs.python.org/3/tutorial/", "Python Documentation", "beginner", "Official language tutorial covering Python fundamentals and standard workflows.", 3),
        ("sql-postgresql", "sql", "PostgreSQL SQL Tutorial", "https://www.postgresql.org/docs/current/tutorial-sql.html", "PostgreSQL Documentation", "beginner", "Official hands-on introduction to relational queries and SQL concepts.", 3),
        ("linux-ubuntu-cli", "linux", "The Linux command line for beginners", "https://documentation.ubuntu.com/desktop/en/latest/tutorial/the-linux-command-line-for-beginners/", "Ubuntu Documentation", "beginner", "Official practical introduction to commands, files, pipes, and permissions.", 3),
        ("git-book", "git", "Pro Git", "https://git-scm.com/book/en/v2", "Git", "beginner", "Official Git book with practical version-control workflows.", 3),
        ("docker-start", "docker", "Docker Get Started", "https://docs.docker.com/get-started/", "Docker Documentation", "beginner", "Official guided introduction to images, containers, and application packaging.", 3),
        ("kubernetes-basics", "kubernetes", "Learn Kubernetes Basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "Kubernetes Documentation", "beginner", "Official interactive overview of deploying and managing containerized applications.", 3),
        ("typescript-handbook", "typescript", "The TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html", "TypeScript Documentation", "beginner", "Official guide to TypeScript's type system and common development patterns.", 3),
        ("office-training", "microsoft-office", "Microsoft 365 training", "https://support.microsoft.com/en-us/training", "Microsoft Support", "beginner", "Official training hub for Excel, Word, PowerPoint, and Microsoft 365.", 3),
        ("physionet-tutorials", "physiological-signals", "PhysioNet Tutorials", "https://physionet.org/about/tutorial/", "PhysioNet", "beginner", "Official hands-on entry point for finding, downloading, and analysing physiological signal datasets.", 3),
        ("physionet-ppg-index", "physiological-signals", "PhysioNet PPG Resources", "https://physionet.org/content/?topic=ppg", "PhysioNet", "review", "Official index of PPG datasets, software, challenges, and tutorials.", 3),
        ("physionet-ptt-ppg", "ppg-blood-pressure", "Pulse Transit Time PPG Dataset", "https://physionet.org/content/pulse-transit-time-ppg/1.0.0/", "PhysioNet", "practice", "Open official dataset with synchronized PPG, ECG, inertial signals, blood pressure, and SpO2 for a bounded hands-on exercise.", 3),
        ("physionet-ppg-databases", "ppg-blood-pressure", "PhysioNet Databases", "https://physionet.org/about/database/", "PhysioNet", "beginner", "Official catalog for selecting physiological waveform datasets before building a PPG baseline.", 3),
        ("mlflow-tracking", "mlflow", "MLflow Tracking Quickstart", "https://mlflow.org/docs/latest/ml/tracking/", "MLflow Documentation", "beginner", "Official quickstart for recording parameters, metrics, artifacts, and repeated model runs.", 3),
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO learning_resources (
            resource_id, topic_id, title, url, source, level, reason, quality_tier,
            last_verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        resources,
    )


def _backfill_saved_job_lineage(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE job_search_runs
        SET resume_profile_id = (
            SELECT p.resume_profile_id
            FROM resume_profiles p
            WHERE p.user_id = job_search_runs.user_id
              AND p.source_confirmed_profile_id = job_search_runs.confirmed_profile_id
            ORDER BY p.updated_at DESC
            LIMIT 1
        )
        WHERE resume_profile_id IS NULL
          AND EXISTS (
            SELECT 1 FROM resume_profiles p
            WHERE p.user_id = job_search_runs.user_id
              AND p.source_confirmed_profile_id = job_search_runs.confirmed_profile_id
          )
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO saved_job_origins (
            saved_job_origin_id, origin_key, user_id, saved_job_id, origin_type,
            resume_profile_id, job_search_run_id, job_search_result_id,
            saved_job_analysis_id, profile_label_snapshot, search_query_snapshot,
            source_provider, created_at
        )
        SELECT
            'origin-' || a.saved_job_analysis_id,
            'analysis:' || a.saved_job_analysis_id,
            a.user_id,
            a.saved_job_id,
            CASE WHEN a.source_job_search_run_id IS NULL THEN 'browser_capture' ELSE 'search_result' END,
            a.resume_profile_id,
            a.source_job_search_run_id,
            a.source_job_result_id,
            a.saved_job_analysis_id,
            p.name,
            r.query,
            j.source_provider,
            a.created_at
        FROM saved_job_analyses a
        JOIN saved_jobs j ON j.saved_job_id = a.saved_job_id
        LEFT JOIN resume_profiles p ON p.resume_profile_id = a.resume_profile_id
        LEFT JOIN job_search_runs r ON r.job_search_run_id = a.source_job_search_run_id
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO saved_job_origins (
            saved_job_origin_id, origin_key, user_id, saved_job_id, origin_type,
            source_provider, created_at
        )
        SELECT
            'origin-manual-' || j.saved_job_id,
            'manual:' || j.saved_job_id,
            j.user_id,
            j.saved_job_id,
            'manual',
            j.source_provider,
            j.saved_at
        FROM saved_jobs j
        WHERE NOT EXISTS (
            SELECT 1 FROM saved_job_origins o WHERE o.saved_job_id = j.saved_job_id
        )
        """
    )


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


def _ensure_local_user(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO users (
            user_id,
            username,
            password_hash,
            password_salt,
            password_algorithm,
            display_name,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            LOCAL_USER_ID,
            LOCAL_USERNAME,
            "local-placeholder",
            "local-placeholder",
            "local-placeholder",
            "Local User",
        ),
    )


def _ensure_user_columns(connection: sqlite3.Connection) -> None:
    for table_name in [
        "profile_sessions",
        "resume_documents",
        "parsed_resume_reviews",
        "profile_drafts",
        "confirmed_profiles",
        "job_search_runs",
    ]:
        _ensure_column(
            connection,
            table_name,
            "user_id",
            f"TEXT DEFAULT '{LOCAL_USER_ID}'",
        )


def _backfill_user_ownership(connection: sqlite3.Connection) -> None:
    for table_name in [
        "profile_sessions",
        "resume_documents",
        "parsed_resume_reviews",
        "profile_drafts",
        "confirmed_profiles",
        "job_search_runs",
    ]:
        connection.execute(
            f"""
            UPDATE {table_name}
            SET user_id = ?
            WHERE user_id IS NULL OR TRIM(user_id) = ''
            """,
            (LOCAL_USER_ID,),
        )


def _backfill_saved_job_status_events(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO saved_job_status_events (
            saved_job_status_event_id,
            saved_job_id,
            user_id,
            from_status,
            to_status,
            reason,
            changed_at
        )
        SELECT
            lower(hex(randomblob(16))),
            saved_job_id,
            user_id,
            NULL,
            status,
            'Initial status backfill',
            saved_at
        FROM saved_jobs AS job
        WHERE NOT EXISTS (
            SELECT 1
            FROM saved_job_status_events AS event
            WHERE event.saved_job_id = job.saved_job_id
              AND event.user_id = job.user_id
        )
        """
    )


def _ensure_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
            ON auth_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash
            ON auth_sessions(token_hash);
        CREATE INDEX IF NOT EXISTS idx_profile_sessions_user_id
            ON profile_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_confirmed_profiles_user_id
            ON confirmed_profiles(user_id);
        CREATE INDEX IF NOT EXISTS idx_job_search_runs_user_id
            ON job_search_runs(user_id);
        CREATE INDEX IF NOT EXISTS idx_job_search_runs_resume_profile
            ON job_search_runs(user_id, resume_profile_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_resume_profiles_user_id
            ON resume_profiles(user_id, archived_at, updated_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_resume_profiles_one_default
            ON resume_profiles(user_id)
            WHERE is_default = 1 AND archived_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_saved_jobs_user_id
            ON saved_jobs(user_id, archived_at, updated_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_jobs_user_source_url
            ON saved_jobs(user_id, source_url)
            WHERE source_url IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_jobs_user_source_key
            ON saved_jobs(user_id, normalized_source_key)
            WHERE normalized_source_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_saved_job_analyses_saved_job_id
            ON saved_job_analyses(saved_job_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_saved_job_origins_job_id
            ON saved_job_origins(user_id, saved_job_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_saved_job_origins_profile
            ON saved_job_origins(user_id, resume_profile_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_job_search_feedback_run_id
            ON job_search_result_feedback(user_id, job_search_run_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_saved_job_status_events_job_id
            ON saved_job_status_events(user_id, saved_job_id, changed_at);
        CREATE INDEX IF NOT EXISTS idx_job_briefs_job_id
            ON job_briefs(user_id, saved_job_id, version);
        CREATE INDEX IF NOT EXISTS idx_interview_preparations_job_id
            ON interview_preparations(user_id, saved_job_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_search_missions_user_session
            ON search_missions(user_id, session_id, status);
        """
    )
