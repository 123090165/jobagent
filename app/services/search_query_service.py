from __future__ import annotations

from app.services.errors import JobAgentError

MIN_QUERY_COUNT = 1
MAX_QUERY_COUNT = 10
_LOCATIONS = ("Shenzhen", "Hong Kong")
_QUERY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("python", "fastapi", "sql"), "Python Backend Engineer"),
    (("llm", "agent", "langgraph", "rag"), "AI Agent Developer"),
    (("streamlit", "fastapi", "api"), "LLM Application Engineer"),
    (("data", "sql", "dashboard"), "Data Analyst"),
    (("embedded", "stm32", "fpga"), "Embedded Software Engineer"),
)
_FALLBACK_QUERIES = (
    "Software Engineer Shenzhen",
    "Graduate Software Engineer Hong Kong",
)


def generate_search_queries_from_resume(
    resume_text: str,
    max_queries: int = 5,
) -> list[str]:
    normalized_resume = resume_text.strip()
    if not normalized_resume:
        raise JobAgentError(
            "Resume text cannot be empty for search query generation",
            "search_query_resume_empty",
        )

    if max_queries < MIN_QUERY_COUNT or max_queries > MAX_QUERY_COUNT:
        raise JobAgentError(
            "Search query count must be between 1 and 10",
            "search_query_limit_invalid",
        )

    lowered_resume = normalized_resume.lower()
    generated_queries: list[str] = []
    for keywords, role_title in _QUERY_RULES:
        if any(keyword in lowered_resume for keyword in keywords):
            for location in _LOCATIONS:
                generated_queries.append(f"{role_title} {location}")

    if not generated_queries:
        generated_queries = list(_FALLBACK_QUERIES)

    return _dedupe_queries(generated_queries)[:max_queries]


def _dedupe_queries(queries: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized_query = query.strip()
        if not normalized_query:
            continue
        dedupe_key = normalized_query.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(normalized_query)
    return deduped
