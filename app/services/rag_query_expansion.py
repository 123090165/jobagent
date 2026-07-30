"""从用户问题和资源上下文生成有限的个人知识检索扩展词。"""

from __future__ import annotations


_CAREER_QUERY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("生理信号", ("physiological signal",)),
    ("机器学习", ("machine learning",)),
    ("向量数据库", ("vector database",)),
    ("向量检索", ("vector retrieval",)),
    ("混合检索", ("hybrid retrieval",)),
    ("后端", ("backend",)),
    ("性能优化", ("performance optimization",)),
    ("接口性能", ("API performance",)),
    ("远程", ("remote",)),
    ("云平台", ("cloud platform",)),
    ("可靠性", ("reliability",)),
)


def expand_personal_knowledge_query(query: str) -> str:
    normalized = query.strip()
    aliases = [
        alias
        for phrase, values in _CAREER_QUERY_ALIASES
        if phrase in normalized
        for alias in values
        if alias.casefold() not in normalized.casefold()
    ]
    if not aliases:
        return normalized
    return f"{normalized}\nSearch aliases: {'; '.join(dict.fromkeys(aliases))}"
