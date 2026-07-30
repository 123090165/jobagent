"""用确定性规则识别重试、比较、最高分职位等需要补充上下文的请求。"""

from __future__ import annotations

from app.schemas.chat import ChatTurn


_FRESH_CONTEXT_TERMS = (
    "最新", "重新看", "重新读取", "刷新", "再查", "latest", "refresh", "reload", "check again",
)
_FIT_CONTEXT_TERMS = (
    "适合我", "匹配我", "匹配度", "合适吗", "fit me", "my fit", "match me", "suitable for me",
)
_RETRY_COMMAND_TERMS = (
    "重试刚刚的问题", "重试上一问", "重新回答刚才的问题", "再回答一次",
    "retry the last question", "retry my last question", "try that again",
)
_RETRY_ACTION_TERMS = (
    "重试", "重新尝试", "再试", "重新回答", "再回答",
    "retry", "try again", "answer again",
)
_PREVIOUS_QUESTION_TERMS = (
    "刚刚", "刚才", "上一问", "上一个问题", "之前的问题", "前面的问题",
    "last question", "previous question", "that again",
)
_CONTINUE_COMMAND_TERMS = (
    "继续", "继续说", "接着说", "继续刚才的问题",
    "continue", "go on", "continue the previous answer",
)


def requires_fresh_context(question: str) -> bool:
    normalized = question.casefold()
    return any(term in normalized for term in _FRESH_CONTEXT_TERMS)


def requires_fit_context(question: str) -> bool:
    normalized = question.casefold()
    return any(term in normalized for term in _FIT_CONTEXT_TERMS)


def requests_highest_saved_job_score(question: str) -> bool:
    normalized = question.casefold()
    return any(term in normalized for term in (
        "评分最高", "最高评分", "分数最高", "最高分", "highest score", "top rated", "top-rated",
    ))


def resolve_conversation_command(
    question: str,
    *,
    recent_turns: list[ChatTurn],
) -> tuple[str, str | None]:
    normalized = " ".join(question.casefold().split())
    if _is_retry_command(normalized):
        previous = _latest_substantive_question(recent_turns)
        return (previous, "retry_previous_question") if previous else (question, None)
    if normalized in _CONTINUE_COMMAND_TERMS:
        previous = _latest_substantive_question(recent_turns)
        return (
            f"继续回答这个问题：{previous}",
            "continue_previous_question",
        ) if previous else (question, None)
    return question, None


def _latest_substantive_question(recent_turns: list[ChatTurn]) -> str | None:
    for turn in reversed(recent_turns):
        candidate = turn.question.strip()
        normalized = " ".join(candidate.casefold().split())
        if not candidate:
            continue
        if _is_retry_command(normalized):
            continue
        if normalized in _CONTINUE_COMMAND_TERMS:
            continue
        return candidate
    return None


def _is_retry_command(normalized: str) -> bool:
    return (
        any(term in normalized for term in _RETRY_COMMAND_TERMS)
        or (
            any(term in normalized for term in _RETRY_ACTION_TERMS)
            and any(term in normalized for term in _PREVIOUS_QUESTION_TERMS)
        )
    )
