from __future__ import annotations

import json

from app.schemas.chat import ChatCitation, ChatTurn
from app.services.chat_context_builder import ChatEvidence
from app.services.llm_provider import JSONChatLLM


HARD_REFUSAL_ANSWER = (
    "我不能协助越权访问其他用户数据、提取密钥、执行 SQL 或系统命令，"
    "也不能绕过确认替你执行外部操作。你可以改为询问已授权资料中的求职问题。"
)


def compress_chat_memory(
    turns: list[ChatTurn],
    *,
    llm_service: JSONChatLLM | None,
) -> dict[str, object]:
    source = [
        {"turn_id": item.turn_id, "question": item.question, "answer": item.answer}
        for item in turns if item.status == "completed"
    ]
    if llm_service is not None:
        try:
            response = llm_service.chat_completion_json(
                system_prompt=(
                    "Compress prior JobAgent chat into JSON with exactly user_goals, preferences, "
                    "decisions, unresolved_questions, referenced_resource_ids; every value is a short "
                    "string array. Do not add facts. This summary is navigation memory, not evidence."
                ),
                user_prompt=json.dumps({"turns": source}, ensure_ascii=False),
            )
            return _bounded_summary(response)
        except (TypeError, ValueError, RuntimeError):
            pass
    return {
        "user_goals": [item["question"][:300] for item in source[-8:]],
        "preferences": [],
        "decisions": [],
        "unresolved_questions": [],
        "referenced_resource_ids": [],
    }


def _bounded_summary(value: dict) -> dict[str, object]:
    keys = ("user_goals", "preferences", "decisions", "unresolved_questions", "referenced_resource_ids")
    result: dict[str, object] = {}
    for key in keys:
        items = value.get(key, [])
        if not isinstance(items, list):
            raise ValueError("invalid summary payload")
        result[key] = [str(item)[:400] for item in items if str(item).strip()][:12]
    return result


def deterministic_chat_answer(
    evidence: list[ChatEvidence],
) -> tuple[str, list[ChatCitation]]:
    if not evidence:
        return (
            "当前模型不可用，且没有可用于回答这个问题的已授权资料。请检查模型配置，"
            "或在会话设置中允许使用相关的 Profile、搜索结果或收藏岗位。",
            [],
        )
    lines = ["当前模型不可用。根据已授权资料，我能先提供这些相关证据："]
    for item in evidence[:5]:
        excerpt = item.citation.excerpt or item.citation.label
        lines.append(f"- {item.citation.label}：{excerpt}")
    lines.append("以上是证据摘录，不是完整的模型分析。")
    return "\n".join(lines), [item.citation for item in evidence[:5]]
