"""读写 SQLite 中的面试准备，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.interview_preparation import (
    InterviewPreparationWorkspace,
    LearningResource,
    PreparationAnswer,
    PreparationGenerationStage,
    PreparationQuestion,
    PreparationRecommendation,
    PreparationSkillGap,
)
from app.storage.database import get_connection, init_database


class InterviewPreparationRepository:
    """封装interview面试准备的 SQLite 读写与模型重建。"""
    def save(self, item: InterviewPreparationWorkspace) -> InterviewPreparationWorkspace:
        """按方法参数限定的主键或用户范围保存相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO interview_preparations (
                    preparation_id, saved_job_id, user_id, resume_profile_id,
                    source_analysis_id, status, skill_gaps_json, questions_json,
                    answers_json, learning_resources_json, recommendations_json,
                    analysis_mode, analysis_provider, fallback_reason,
                    question_generation_json, recommendation_generation_json,
                    resource_mode, resource_warning, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, saved_job_id) DO UPDATE SET
                    resume_profile_id = excluded.resume_profile_id,
                    source_analysis_id = excluded.source_analysis_id,
                    status = excluded.status,
                    skill_gaps_json = excluded.skill_gaps_json,
                    questions_json = excluded.questions_json,
                    answers_json = excluded.answers_json,
                    learning_resources_json = excluded.learning_resources_json,
                    recommendations_json = excluded.recommendations_json,
                    analysis_mode = excluded.analysis_mode,
                    analysis_provider = excluded.analysis_provider,
                    fallback_reason = excluded.fallback_reason,
                    question_generation_json = excluded.question_generation_json,
                    recommendation_generation_json = excluded.recommendation_generation_json,
                    resource_mode = excluded.resource_mode,
                    resource_warning = excluded.resource_warning,
                    updated_at = excluded.updated_at
                """,
                self._values(item),
            )
            connection.commit()
        return self.get(user_id=item.user_id, saved_job_id=item.saved_job_id) or item

    def create(
        self, *, user_id: str, saved_job_id: str, resume_profile_id: str | None,
        source_analysis_id: str | None, skill_gaps: list[PreparationSkillGap],
        questions: list[PreparationQuestion], learning_resources: list[LearningResource],
        analysis_mode: str, analysis_provider: str | None, fallback_reason: str | None,
        question_generation: PreparationGenerationStage,
        resource_mode: str, resource_warning: str | None,
    ) -> InterviewPreparationWorkspace:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        existing = self.get(user_id=user_id, saved_job_id=saved_job_id)
        now = datetime.now(timezone.utc)
        return self.save(InterviewPreparationWorkspace(
            preparation_id=existing.preparation_id if existing else str(uuid4()),
            saved_job_id=saved_job_id, user_id=user_id,
            resume_profile_id=resume_profile_id, source_analysis_id=source_analysis_id,
            status="questions_ready", skill_gaps=skill_gaps, questions=questions,
            answers=[], learning_resources=learning_resources, recommendations=[],
            analysis_mode=analysis_mode, analysis_provider=analysis_provider,
            fallback_reason=fallback_reason,
            question_generation=question_generation,
            recommendation_generation=None,
            resource_mode=resource_mode,
            resource_warning=resource_warning,
            created_at=existing.created_at if existing else now, updated_at=now,
        ))

    def complete(
        self, item: InterviewPreparationWorkspace, *, answers: list[PreparationAnswer],
        recommendations: list[PreparationRecommendation], analysis_mode: str,
        analysis_provider: str | None, fallback_reason: str | None,
        recommendation_generation: PreparationGenerationStage,
        learning_resources: list[LearningResource] | None = None,
        resource_mode: str | None = None, resource_warning: str | None = None,
    ) -> InterviewPreparationWorkspace:
        """按方法参数限定的主键或用户范围完成相关数据。"""
        return self.save(item.model_copy(update={
            "status": "completed", "answers": answers,
            "recommendations": recommendations, "analysis_mode": analysis_mode,
            "analysis_provider": analysis_provider, "fallback_reason": fallback_reason,
            "recommendation_generation": recommendation_generation,
            "learning_resources": learning_resources if learning_resources is not None else item.learning_resources,
            "resource_mode": resource_mode or item.resource_mode,
            "resource_warning": resource_warning,
            "updated_at": datetime.now(timezone.utc),
        }))

    def save_answers(
        self, item: InterviewPreparationWorkspace, *, answers: list[PreparationAnswer],
        status: str,
    ) -> InterviewPreparationWorkspace:
        """按方法参数限定的主键或用户范围保存answers。"""
        return self.save(item.model_copy(update={
            "status": status,
            "answers": answers,
            "recommendations": [] if status != "completed" else item.recommendations,
            "updated_at": datetime.now(timezone.utc),
        }))

    def get(self, *, user_id: str, saved_job_id: str) -> InterviewPreparationWorkspace | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                "SELECT * FROM interview_preparations WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            ).fetchone()
        return self._row(row) if row else None

    @staticmethod
    def _values(item: InterviewPreparationWorkspace) -> tuple[object, ...]:
        dump = lambda values: json.dumps([value.model_dump(mode="json") for value in values])
        return (
            item.preparation_id, item.saved_job_id, item.user_id, item.resume_profile_id,
            item.source_analysis_id, item.status, dump(item.skill_gaps), dump(item.questions),
            dump(item.answers), dump(item.learning_resources), dump(item.recommendations),
            item.analysis_mode, item.analysis_provider, item.fallback_reason,
            _dump_stage(item.question_generation),
            _dump_stage(item.recommendation_generation),
            item.resource_mode, item.resource_warning, item.created_at.isoformat(),
            item.updated_at.isoformat(),
        )

    @staticmethod
    def _row(row: object) -> InterviewPreparationWorkspace:
        load = lambda key, model: [model.model_validate(item) for item in json.loads(row[key] or "[]")]
        return InterviewPreparationWorkspace(
            preparation_id=row["preparation_id"], saved_job_id=row["saved_job_id"],
            user_id=row["user_id"], resume_profile_id=row["resume_profile_id"],
            source_analysis_id=row["source_analysis_id"], status=row["status"],
            skill_gaps=load("skill_gaps_json", PreparationSkillGap),
            questions=load("questions_json", PreparationQuestion),
            answers=load("answers_json", PreparationAnswer),
            learning_resources=load("learning_resources_json", LearningResource),
            recommendations=load("recommendations_json", PreparationRecommendation),
            analysis_mode=row["analysis_mode"], analysis_provider=row["analysis_provider"],
            fallback_reason=row["fallback_reason"],
            question_generation=_load_stage(row, "question_generation_json"),
            recommendation_generation=_load_stage(row, "recommendation_generation_json"),
            resource_mode=row["resource_mode"],
            resource_warning=row["resource_warning"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def _dump_stage(stage: PreparationGenerationStage | None) -> str | None:
    return json.dumps(stage.model_dump(mode="json")) if stage else None


def _load_stage(row: object, key: str) -> PreparationGenerationStage | None:
    raw = row[key]
    return PreparationGenerationStage.model_validate(json.loads(raw)) if raw else None


interview_preparation_repository = InterviewPreparationRepository()
