"""读写 SQLite 中的Assistant 会话、消息与上下文，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.chat import (
    ChatCitation,
    ChatConversation,
    ChatConversationCreateRequest,
    ChatConversationUpdateRequest,
    ChatDataScope,
    ChatRouteDecision,
    ChatRetrievalPlan,
    ChatSearchResultRef,
    ChatSource,
    ChatTurn,
    ChatTurnAttachment,
)
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatRepository:
    """封装对话的 SQLite 读写与模型重建。"""
    def create_conversation(
        self,
        *,
        user_id: str,
        payload: ChatConversationCreateRequest,
    ) -> ChatConversation:
        """按方法参数限定的主键或用户范围创建会话。"""
        now = _utc_now()
        conversation = ChatConversation(
            conversation_id=str(uuid4()),
            user_id=user_id,
            title=payload.title or "New conversation",
            data_access_mode=payload.data_access_mode,
            data_scope=payload.data_scope,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO chat_conversations (
                    conversation_id, user_id, title, title_is_auto, data_access_mode,
                    data_scope_json, summary_json, summary_through_sequence,
                    summary_version, last_retrieval_used,
                    last_retrieval_sources_json, last_completed_sequence,
                    next_sequence, created_at, updated_at
                ) VALUES (?, ?, ?, 0, ?, ?, '{}', 0, 0, 0, '[]', 0, 1, ?, ?)
                """,
                (
                    conversation.conversation_id,
                    user_id,
                    conversation.title,
                    conversation.data_access_mode,
                    json.dumps(conversation.data_scope.model_dump(mode="json")),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.commit()
        return conversation

    def get_conversation(self, *, user_id: str, conversation_id: str) -> ChatConversation | None:
        """按方法参数限定的主键或用户范围获取会话。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                "SELECT * FROM chat_conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            ).fetchone()
        return self._row_to_conversation(row) if row is not None else None

    def list_conversations(self, *, user_id: str, limit: int = 50) -> list[ChatConversation]:
        """按方法参数限定的主键或用户范围列出conversations。"""
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT * FROM chat_conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_conversation(row) for row in rows]

    def update_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
        payload: ChatConversationUpdateRequest,
    ) -> ChatConversation | None:
        """按方法参数限定的主键或用户范围更新会话。"""
        existing = self.get_conversation(user_id=user_id, conversation_id=conversation_id)
        if existing is None:
            return None
        title = payload.title.strip() if payload.title and payload.title.strip() else existing.title
        access_mode = payload.data_access_mode or existing.data_access_mode
        data_scope = payload.data_scope or existing.data_scope
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE chat_conversations
                SET title = ?,
                    title_is_auto = CASE WHEN ? THEN 0 ELSE title_is_auto END,
                    data_access_mode = ?, data_scope_json = ?, updated_at = ?
                WHERE user_id = ? AND conversation_id = ?
                """,
                (
                    title,
                    int(payload.title is not None and bool(payload.title.strip())),
                    access_mode,
                    json.dumps(data_scope.model_dump(mode="json")),
                    now.isoformat(),
                    user_id,
                    conversation_id,
                ),
            )
            connection.commit()
        return self.get_conversation(user_id=user_id, conversation_id=conversation_id)

    def pin_search_result(
        self,
        *,
        user_id: str,
        conversation_id: str,
        ref: ChatSearchResultRef,
        max_refs: int = 20,
    ) -> ChatConversation | None:
        """按方法参数限定的主键或用户范围处理pin搜索结果。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM chat_conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            scope = ChatDataScope.model_validate(json.loads(row["data_scope_json"]))
            refs = scope.job_search_result_refs
            if any(
                item.job_search_run_id == ref.job_search_run_id
                and item.job_result_id == ref.job_result_id
                for item in refs
            ):
                connection.commit()
                return self._row_to_conversation(row)
            if len(refs) >= max_refs:
                connection.rollback()
                raise OverflowError("chat search-result pin limit reached")
            updated_scope = scope.model_copy(update={"job_search_result_refs": [*refs, ref]})
            connection.execute(
                """
                UPDATE chat_conversations
                SET data_scope_json = ?, updated_at = ?
                WHERE user_id = ? AND conversation_id = ?
                """,
                (
                    json.dumps(updated_scope.model_dump(mode="json")),
                    now.isoformat(),
                    user_id,
                    conversation_id,
                ),
            )
            updated_row = connection.execute(
                "SELECT * FROM chat_conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            ).fetchone()
            connection.commit()
        return self._row_to_conversation(updated_row)

    def create_pending_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        client_turn_id: str,
        question: str,
        context_attachments: list[ChatTurnAttachment] | None = None,
        retry_of_turn_id: str | None = None,
    ) -> ChatTurn | None:
        """按方法参数限定的主键或用户范围创建pending消息轮次。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                "SELECT 1 FROM chat_conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            ).fetchone()
            if owner is None:
                connection.rollback()
                return None
            existing = connection.execute(
                """
                SELECT * FROM chat_turns
                WHERE user_id = ? AND conversation_id = ? AND client_turn_id = ?
                """,
                (user_id, conversation_id, client_turn_id),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return self._row_to_turn(existing)
            row = connection.execute(
                """
                SELECT next_sequence FROM chat_conversations
                WHERE user_id = ? AND conversation_id = ?
                """,
                (user_id, conversation_id),
            ).fetchone()
            turn = ChatTurn(
                turn_id=str(uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                sequence=int(row["next_sequence"]),
                client_turn_id=client_turn_id,
                question=question,
                status="pending",
                context_attachments=context_attachments or [],
                retry_of_turn_id=retry_of_turn_id,
                created_at=now,
                updated_at=now,
            )
            connection.execute(
                """
                INSERT INTO chat_turns (
                    turn_id, conversation_id, user_id, sequence, client_turn_id,
                    question, answer, status, route_json, retrieval_plan_json, retrieval_used,
                    retrieved_refs_json, citations_json, analysis_mode,
                    analysis_provider, fallback_reason, quality_warnings_json,
                    context_attachments_json, retry_of_turn_id, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, NULL, 'pending', NULL, NULL, 0, '[]', '[]',
                    NULL, NULL, NULL, '[]', ?, ?, ?, ?
                )
                """,
                (
                    turn.turn_id,
                    conversation_id,
                    user_id,
                    turn.sequence,
                    client_turn_id,
                    question,
                    json.dumps([
                        item.model_dump(mode="json") for item in (context_attachments or [])
                    ]),
                    retry_of_turn_id,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE chat_conversations
                SET next_sequence = ?, updated_at = ?
                WHERE user_id = ? AND conversation_id = ?
                """,
                (turn.sequence + 1, now.isoformat(), user_id, conversation_id),
            )
            connection.commit()
        return turn

    def complete_turn(
        self,
        *,
        user_id: str,
        turn: ChatTurn,
        route: ChatRouteDecision,
        retrieval_plan: ChatRetrievalPlan,
        answer: str,
        retrieval_used: bool,
        retrieved_refs: list[str],
        citations: list[ChatCitation],
        analysis_mode: str,
        analysis_provider: str | None,
        fallback_reason: str | None,
        quality_warnings: list[str],
    ) -> ChatTurn | None:
        """按方法参数限定的主键或用户范围完成消息轮次。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE chat_turns
                SET answer = ?, status = 'completed', route_json = ?, retrieval_plan_json = ?,
                    retrieval_used = ?, retrieved_refs_json = ?, citations_json = ?,
                    analysis_mode = ?, analysis_provider = ?, fallback_reason = ?,
                    quality_warnings_json = ?, updated_at = ?
                WHERE user_id = ? AND conversation_id = ? AND turn_id = ?
                """,
                (
                    answer,
                    json.dumps(route.model_dump(mode="json")),
                    json.dumps(retrieval_plan.model_dump(mode="json")),
                    int(retrieval_used),
                    json.dumps(retrieved_refs),
                    json.dumps([item.model_dump(mode="json") for item in citations]),
                    analysis_mode,
                    analysis_provider,
                    fallback_reason,
                    json.dumps(quality_warnings),
                    now.isoformat(),
                    user_id,
                    turn.conversation_id,
                    turn.turn_id,
                ),
            )
            if cursor.rowcount == 0:
                connection.rollback()
                return None
            title = _derived_title(turn.question)
            connection.execute(
                """
                UPDATE chat_conversations
                SET title = CASE
                        WHEN title_is_auto = 0 AND title = 'New conversation' THEN ?
                        ELSE title
                    END,
                    title_is_auto = CASE WHEN title_is_auto = 0 AND title = 'New conversation' THEN 1 ELSE title_is_auto END,
                    last_retrieval_used = ?, last_retrieval_sources_json = ?,
                    last_completed_sequence = ?, updated_at = ?
                WHERE user_id = ? AND conversation_id = ?
                """,
                (
                    title,
                    int(retrieval_used),
                    json.dumps(route.retrieval if retrieval_used else []),
                    turn.sequence,
                    now.isoformat(),
                    user_id,
                    turn.conversation_id,
                ),
            )
            connection.commit()
        return self.get_turn(user_id=user_id, conversation_id=turn.conversation_id, turn_id=turn.turn_id)

    def fail_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        turn_id: str,
        fallback_reason: str,
    ) -> ChatTurn | None:
        """按方法参数限定的主键或用户范围标记失败消息轮次。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE chat_turns
                SET status = 'failed', fallback_reason = ?, updated_at = ?
                WHERE user_id = ? AND conversation_id = ? AND turn_id = ?
                """,
                (fallback_reason, now.isoformat(), user_id, conversation_id, turn_id),
            )
            connection.commit()
        return self.get_turn(user_id=user_id, conversation_id=conversation_id, turn_id=turn_id)

    def get_turn(self, *, user_id: str, conversation_id: str, turn_id: str) -> ChatTurn | None:
        """按方法参数限定的主键或用户范围获取消息轮次。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT * FROM chat_turns
                WHERE user_id = ? AND conversation_id = ? AND turn_id = ?
                """,
                (user_id, conversation_id, turn_id),
            ).fetchone()
        return self._row_to_turn(row) if row is not None else None

    def get_latest_completed_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
    ) -> ChatTurn | None:
        """按方法参数限定的主键或用户范围获取latestcompleted消息轮次。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT * FROM chat_turns
                WHERE user_id = ? AND conversation_id = ? AND status = 'completed'
                ORDER BY sequence DESC LIMIT 1
                """,
                (user_id, conversation_id),
            ).fetchone()
        return self._row_to_turn(row) if row is not None else None

    def list_turns(
        self,
        *,
        user_id: str,
        conversation_id: str,
        limit: int = 50,
        before_sequence: int | None = None,
    ) -> list[ChatTurn]:
        """按方法参数限定的主键或用户范围列出turns。"""
        where = "WHERE user_id = ? AND conversation_id = ?"
        parameters: list[object] = [user_id, conversation_id]
        if before_sequence is not None:
            where += " AND sequence < ?"
            parameters.append(before_sequence)
        parameters.append(limit)
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                f"SELECT * FROM chat_turns {where} ORDER BY sequence DESC LIMIT ?",
                tuple(parameters),
            ).fetchall()
        return [self._row_to_turn(row) for row in reversed(rows)]

    def count_completed_turns(
        self,
        *,
        user_id: str,
        conversation_id: str,
        after_sequence: int | None = None,
    ) -> int:
        """按方法参数限定的主键或用户范围处理countcompletedturns。"""
        where = "WHERE user_id = ? AND conversation_id = ? AND status = 'completed'"
        parameters: list[object] = [user_id, conversation_id]
        if after_sequence is not None:
            where += " AND sequence > ?"
            parameters.append(after_sequence)
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM chat_turns {where}",
                tuple(parameters),
            ).fetchone()
        return int(row["count"])

    def update_summary(
        self,
        *,
        user_id: str,
        conversation_id: str,
        summary: dict[str, object],
        through_sequence: int,
    ) -> ChatConversation | None:
        """按方法参数限定的主键或用户范围更新summary。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE chat_conversations
                SET summary_json = ?, summary_through_sequence = ?,
                    summary_version = summary_version + 1, updated_at = ?
                WHERE user_id = ? AND conversation_id = ?
                """,
                (json.dumps(summary), through_sequence, now.isoformat(), user_id, conversation_id),
            )
            connection.commit()
        return self.get_conversation(user_id=user_id, conversation_id=conversation_id)

    def delete_turn(self, *, user_id: str, conversation_id: str, turn_id: str) -> bool:
        """按方法参数限定的主键或用户范围删除消息轮次。"""
        with get_connection() as connection:
            init_database(connection)
            connection.execute("BEGIN IMMEDIATE")
            deleted = connection.execute(
                """
                DELETE FROM chat_turns
                WHERE user_id = ? AND conversation_id = ? AND turn_id = ?
                """,
                (user_id, conversation_id, turn_id),
            )
            if deleted.rowcount == 0:
                connection.rollback()
                return False
            self._reset_derived_memory(connection, user_id=user_id, conversation_id=conversation_id)
            connection.commit()
        return True

    def clear_memory(self, *, user_id: str, conversation_id: str) -> bool:
        """按方法参数限定的主键或用户范围清空记忆。"""
        with get_connection() as connection:
            init_database(connection)
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                "SELECT 1 FROM chat_conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            ).fetchone()
            if owner is None:
                connection.rollback()
                return False
            connection.execute(
                "DELETE FROM chat_turns WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            now = _utc_now().isoformat()
            connection.execute(
                """
                UPDATE chat_conversations
                SET title = 'New conversation', title_is_auto = 0, summary_json = '{}',
                    summary_through_sequence = 0, summary_version = summary_version + 1,
                    last_retrieval_used = 0, last_retrieval_sources_json = '[]',
                    last_completed_sequence = 0, next_sequence = 1, updated_at = ?
                WHERE user_id = ? AND conversation_id = ?
                """,
                (now, user_id, conversation_id),
            )
            connection.commit()
        return True

    def delete_conversation(self, *, user_id: str, conversation_id: str) -> bool:
        """按方法参数限定的主键或用户范围删除会话。"""
        with get_connection() as connection:
            init_database(connection)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM chat_turns WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            deleted = connection.execute(
                "DELETE FROM chat_conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            connection.commit()
        return deleted.rowcount > 0

    @staticmethod
    def _reset_derived_memory(connection: sqlite3.Connection, *, user_id: str, conversation_id: str) -> None:
        conversation = connection.execute(
            """
            SELECT title_is_auto FROM chat_conversations
            WHERE user_id = ? AND conversation_id = ?
            """,
            (user_id, conversation_id),
        ).fetchone()
        latest = connection.execute(
            """
            SELECT sequence, retrieval_used, route_json
            FROM chat_turns
            WHERE user_id = ? AND conversation_id = ? AND status = 'completed'
            ORDER BY sequence DESC LIMIT 1
            """,
            (user_id, conversation_id),
        ).fetchone()
        sequence = int(latest["sequence"]) if latest is not None else 0
        retrieval_used = bool(latest["retrieval_used"]) if latest is not None else False
        sources: list[ChatSource] = []
        if latest is not None and latest["route_json"]:
            sources = ChatRouteDecision.model_validate(json.loads(latest["route_json"])).retrieval
        earliest = connection.execute(
            """
            SELECT question FROM chat_turns
            WHERE user_id = ? AND conversation_id = ? AND status = 'completed'
            ORDER BY sequence ASC LIMIT 1
            """,
            (user_id, conversation_id),
        ).fetchone()
        replacement_title = _derived_title(earliest["question"]) if earliest is not None else "New conversation"
        title_is_auto = bool(conversation["title_is_auto"]) if conversation is not None else False
        connection.execute(
            """
            UPDATE chat_conversations
            SET title = CASE WHEN ? THEN ? ELSE title END,
                title_is_auto = CASE WHEN ? THEN ? ELSE title_is_auto END,
                summary_json = '{}', summary_through_sequence = 0,
                summary_version = summary_version + 1,
                last_retrieval_used = ?, last_retrieval_sources_json = ?,
                last_completed_sequence = ?, updated_at = ?
            WHERE user_id = ? AND conversation_id = ?
            """,
            (
                int(title_is_auto),
                replacement_title,
                int(title_is_auto),
                int(earliest is not None),
                int(retrieval_used),
                json.dumps(sources if retrieval_used else []),
                sequence,
                _utc_now().isoformat(),
                user_id,
                conversation_id,
            ),
        )

    @staticmethod
    def _row_to_conversation(row: object) -> ChatConversation:
        return ChatConversation(
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            title=row["title"],
            data_access_mode=row["data_access_mode"],
            data_scope=ChatDataScope.model_validate(json.loads(row["data_scope_json"])),
            summary=json.loads(row["summary_json"]),
            summary_through_sequence=int(row["summary_through_sequence"]),
            summary_version=int(row["summary_version"]),
            last_retrieval_used=bool(row["last_retrieval_used"]),
            last_retrieval_sources=json.loads(row["last_retrieval_sources_json"]),
            last_completed_sequence=int(row["last_completed_sequence"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_turn(row: object) -> ChatTurn:
        route = (
            ChatRouteDecision.model_validate(json.loads(row["route_json"]))
            if row["route_json"]
            else None
        )
        retrieval_plan = (
            ChatRetrievalPlan.model_validate(json.loads(row["retrieval_plan_json"]))
            if row["retrieval_plan_json"]
            else None
        )
        return ChatTurn(
            turn_id=row["turn_id"],
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            sequence=int(row["sequence"]),
            client_turn_id=row["client_turn_id"],
            question=row["question"],
            answer=row["answer"],
            status=row["status"],
            route=route,
            retrieval_plan=retrieval_plan,
            retrieval_used=bool(row["retrieval_used"]),
            retrieved_refs=json.loads(row["retrieved_refs_json"]),
            citations=[ChatCitation.model_validate(item) for item in json.loads(row["citations_json"])],
            analysis_mode=row["analysis_mode"],
            analysis_provider=row["analysis_provider"],
            fallback_reason=row["fallback_reason"],
            quality_warnings=json.loads(row["quality_warnings_json"]),
            context_attachments=json.loads(row["context_attachments_json"]),
            retry_of_turn_id=row["retry_of_turn_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def _derived_title(question: str) -> str:
    compact = " ".join(question.split())
    return compact[:60] + ("…" if len(compact) > 60 else "")


chat_repository = ChatRepository()
