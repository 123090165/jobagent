"""读写 SQLite 中的简历解析审阅，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.parsed_resume_review import ParsedResumeReview
from app.storage.database import LOCAL_USER_ID, get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ParsedResumeReviewRepository:
    """封装parsed简历审阅结果的 SQLite 读写与模型重建。"""
    def create(
        self,
        *,
        session_id: str,
        resume_document_id: str,
        basic_info: dict,
        education: list[dict],
        work_experience: list[dict],
        projects: list[dict],
        skills: dict,
        target_signals: list[str],
        quality_warnings: list[str],
        missing_info_questions: list[str],
        raw_parser_output: dict | None,
        user_id: str = LOCAL_USER_ID,
        analysis_mode: str = "deterministic",
        analysis_provider: str | None = None,
        analysis_warnings: list[str] | None = None,
    ) -> ParsedResumeReview:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        now = _utc_now()
        review = ParsedResumeReview(
            parsed_review_id=str(uuid4()),
            session_id=session_id,
            resume_document_id=resume_document_id,
            basic_info=basic_info,
            education=education,
            work_experience=work_experience,
            projects=projects,
            skills=skills,
            target_signals=target_signals,
            quality_warnings=quality_warnings,
            missing_info_questions=missing_info_questions,
            raw_parser_output=raw_parser_output,
            analysis_mode=analysis_mode,  # type: ignore[arg-type]
            analysis_provider=analysis_provider,
            analysis_warnings=analysis_warnings or [],
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO parsed_resume_reviews (
                    parsed_review_id,
                    session_id,
                    resume_document_id,
                    user_id,
                    basic_info_json,
                    education_json,
                    work_experience_json,
                    projects_json,
                    skills_json,
                    target_signals_json,
                    quality_warnings_json,
                    missing_info_questions_json,
                    raw_parser_output_json,
                    analysis_mode,
                    analysis_provider,
                    analysis_warnings_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.parsed_review_id,
                    review.session_id,
                    review.resume_document_id,
                    user_id,
                    json.dumps(review.basic_info),
                    json.dumps(review.education),
                    json.dumps(review.work_experience),
                    json.dumps(review.projects),
                    json.dumps(review.skills),
                    json.dumps(review.target_signals),
                    json.dumps(review.quality_warnings),
                    json.dumps(review.missing_info_questions),
                    json.dumps(review.raw_parser_output) if review.raw_parser_output is not None else None,
                    review.analysis_mode,
                    review.analysis_provider,
                    json.dumps(review.analysis_warnings),
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return review

    def get(self, parsed_review_id: str, *, user_id: str | None = None) -> ParsedResumeReview | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE parsed_review_id = ?"
            parameters: tuple[str, ...] = (parsed_review_id,)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (parsed_review_id, user_id)
            row = connection.execute(
                f"""
                SELECT
                    parsed_review_id,
                    session_id,
                    resume_document_id,
                    basic_info_json,
                    education_json,
                    work_experience_json,
                    projects_json,
                    skills_json,
                    target_signals_json,
                    quality_warnings_json,
                    missing_info_questions_json,
                    raw_parser_output_json,
                    analysis_mode,
                    analysis_provider,
                    analysis_warnings_json,
                    created_at,
                    updated_at
                FROM parsed_resume_reviews
                {where_clause}
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return self._row_to_review(row)

    def get_current_for_session(
        self,
        *,
        session_id: str,
        resume_document_id: str,
        user_id: str | None = None,
    ) -> ParsedResumeReview | None:
        """按方法参数限定的主键或用户范围获取currentfor会话。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE session_id = ? AND resume_document_id = ?"
            parameters: tuple[str, ...] = (session_id, resume_document_id)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (session_id, resume_document_id, user_id)
            row = connection.execute(
                f"""
                SELECT
                    parsed_review_id,
                    session_id,
                    resume_document_id,
                    basic_info_json,
                    education_json,
                    work_experience_json,
                    projects_json,
                    skills_json,
                    target_signals_json,
                    quality_warnings_json,
                    missing_info_questions_json,
                    raw_parser_output_json,
                    analysis_mode,
                    analysis_provider,
                    analysis_warnings_json,
                    created_at,
                    updated_at
                FROM parsed_resume_reviews
                {where_clause}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return self._row_to_review(row)

    @staticmethod
    def _row_to_review(row: object) -> ParsedResumeReview:
        return ParsedResumeReview(
            parsed_review_id=row["parsed_review_id"],
            session_id=row["session_id"],
            resume_document_id=row["resume_document_id"],
            basic_info=json.loads(row["basic_info_json"]),
            education=json.loads(row["education_json"]),
            work_experience=json.loads(row["work_experience_json"]),
            projects=json.loads(row["projects_json"]),
            skills=json.loads(row["skills_json"]),
            target_signals=json.loads(row["target_signals_json"]),
            quality_warnings=json.loads(row["quality_warnings_json"]),
            missing_info_questions=json.loads(row["missing_info_questions_json"]),
            raw_parser_output=(
                json.loads(row["raw_parser_output_json"])
                if row["raw_parser_output_json"] is not None
                else None
            ),
            analysis_mode=row["analysis_mode"] or "deterministic",
            analysis_provider=row["analysis_provider"] if "analysis_provider" in row.keys() else None,
            analysis_warnings=json.loads(row["analysis_warnings_json"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


parsed_resume_review_repository = ParsedResumeReviewRepository()
