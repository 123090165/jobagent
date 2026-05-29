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
            match_report_id INTEGER NOT NULL,
            project_challenge_id INTEGER NOT NULL,
            optimization_json TEXT NOT NULL,
            markdown_report TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resume_record_id) REFERENCES resume_records(id),
            FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
            FOREIGN KEY (match_report_id) REFERENCES match_reports(id),
            FOREIGN KEY (project_challenge_id) REFERENCES project_challenges(id)
        );

        CREATE TABLE IF NOT EXISTS application_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_posting_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'interested',
            notes TEXT,
            next_action TEXT,
            resume_version_label TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_posting_id) REFERENCES job_postings(id)
        );
        """
    )
    connection.commit()
