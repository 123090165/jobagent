"""读写 SQLite 中的学习资源，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json

from app.schemas.interview_preparation import LearningResource
from app.storage.database import get_connection, init_database


class LearningResourceRepository:
    """封装学习资源的 SQLite 读写与模型重建。"""
    def search(self, topic: str, *, limit: int = 2) -> list[LearningResource]:
        """按方法参数限定的主键或用户范围搜索相关数据。"""
        normalized = topic.casefold().strip()
        with get_connection() as connection:
            init_database(connection)
            topics = connection.execute(
                "SELECT topic_id, canonical_name, aliases_json FROM learning_topics"
            ).fetchall()
            topic_ids = [
                row["topic_id"] for row in topics
                if _matches(normalized, row["canonical_name"], row["aliases_json"])
            ]
            if not topic_ids:
                return []
            placeholders = ",".join("?" for _ in topic_ids)
            rows = connection.execute(
                f"""
                SELECT r.*, t.canonical_name
                FROM learning_resources r
                JOIN learning_topics t ON t.topic_id = r.topic_id
                WHERE r.topic_id IN ({placeholders}) AND r.is_curated = 1
                ORDER BY r.quality_tier DESC, r.title ASC
                LIMIT ?
                """,
                (*topic_ids, limit),
            ).fetchall()
        return [
            LearningResource(
                topic=topic,
                title=row["title"],
                url=row["url"],
                source=row["source"],
                level=row["level"],
                reason=row["reason"],
            )
            for row in rows
        ]


def _matches(query: str, canonical_name: str, aliases_json: str) -> bool:
    names = [canonical_name, *json.loads(aliases_json or "[]")]
    return any(name.casefold() in query or query in name.casefold() for name in names)


learning_resource_repository = LearningResourceRepository()
