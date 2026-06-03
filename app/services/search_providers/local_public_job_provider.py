from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.search import SearchResultItem, SearchResultSet
from app.services.public_job_storage_service import list_public_job_posts
from app.services.search_providers.base import SearchProvider

QUALITY_BONUS = {
    "full_jd": 3.0,
    "partial_jd": 1.0,
    "external_link_only": -1.0,
    "snippet_only": -2.0,
    "invalid": -5.0,
}
SECTION_BREAK_HEADINGS = [
    "responsibilities",
    "requirements",
    "qualifications",
    "skills",
    "岗位职责",
    "工作职责",
    "任职要求",
    "岗位要求",
    "职责",
    "要求",
    "技能",
]

RESPONSIBILITY_HEADINGS = ["responsibilities", "responsibility", "岗位职责", "工作职责", "职责"]
REQUIREMENT_HEADINGS = ["requirements", "requirement", "qualifications", "任职要求", "岗位要求", "要求"]
SKILL_LINE_HEADINGS = ["skills", "skill", "技能"]
SKILL_KEYWORDS = [
    "Python",
    "FastAPI",
    "Pydantic",
    "SQL",
    "LLM",
    "AI",
    "Machine Learning",
    "Deep Learning",
    "Data Analysis",
    "REST API",
    "HTTP",
    "Testing",
    "Java",
    "C++",
    "Go",
]


class LocalPublicJobProvider(SearchProvider):
    name = "local_db"

    def __init__(self, *, database_path: str | Path | None = None) -> None:
        self._database_path = database_path

    def search_jobs(self, query: str, limit: int = 5) -> SearchResultSet:
        rows = list_public_job_posts(
            keyword=query,
            limit=max(limit * 5, 20),
            database_path=self._database_path,
        )
        ranked_rows = _rank_rows(rows, query)
        valid_rows = [row for row in ranked_rows if _get_quality_label(row) != "invalid"]
        selected_rows = (valid_rows or ranked_rows)[:limit]
        return SearchResultSet(
            query=query,
            provider=self.name,
            items=[_row_to_search_result(row) for row in selected_rows],
        )


def _row_to_search_result(row: dict[str, object]) -> SearchResultItem:
    jd_text = str(row.get("jd_text") or "").strip()
    snippet = str(row.get("snippet") or "").strip() or jd_text[:300]
    return SearchResultItem(
        title=str(row.get("title") or "").strip(),
        company=str(row.get("company") or "").strip(),
        location=str(row.get("location") or "").strip(),
        url=str(row.get("source_url") or "").strip(),
        snippet=snippet,
        source=str(row.get("source") or "local_db").strip(),
        retrieved_at=_parse_retrieved_at(row.get("fetched_at")),
        responsibilities=_extract_section_lines(jd_text, RESPONSIBILITY_HEADINGS),
        requirements=_extract_section_lines(jd_text, REQUIREMENT_HEADINGS),
        skills=_extract_skills(jd_text),
        jd_text=jd_text or None,
        is_full_jd=_get_quality_label(row) == "full_jd",
        confidence=_coerce_confidence(row.get("quality_score", row.get("confidence"))),
        quality_label=_get_quality_label(row),
        warnings=_normalize_string_list(row.get("quality_warnings")),
        external_links=_normalize_string_list(row.get("external_links")),
    )


def _parse_retrieved_at(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc)

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _rank_rows(rows: list[dict[str, object]], query: str) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            _build_row_score(row, query),
            _coerce_confidence(row.get("quality_score", row.get("confidence"))),
            str(row.get("updated_at") or ""),
            int(row.get("id") or 0),
        ),
        reverse=True,
    )


def _build_row_score(row: dict[str, object], query: str) -> float:
    keyword_hit_score = _keyword_hit_score(row, query)
    quality_label = _get_quality_label(row)
    quality_bonus = QUALITY_BONUS.get(quality_label, 0.0)
    confidence_bonus = _coerce_confidence(row.get("quality_score", row.get("confidence")))
    return keyword_hit_score + quality_bonus + confidence_bonus


def _keyword_hit_score(row: dict[str, object], query: str) -> float:
    haystacks = [
        str(row.get("title") or ""),
        str(row.get("company") or ""),
        str(row.get("location") or ""),
        str(row.get("snippet") or ""),
        str(row.get("jd_text") or ""),
    ]
    searchable_text = "\n".join(haystacks).lower()
    query_terms = [term.strip().lower() for term in str(query or "").split() if term.strip()]
    if not query_terms:
        query_terms = [str(query or "").strip().lower()] if str(query or "").strip() else []

    score = 0.0
    for term in query_terms:
        occurrences = searchable_text.count(term)
        if not occurrences:
            continue
        score += min(occurrences, 3)
        if term in str(row.get("title") or "").lower():
            score += 1.5
    return score


def _get_quality_label(row: dict[str, object]) -> str:
    quality_label = str(row.get("quality_label") or "").strip()
    if quality_label:
        return quality_label
    if bool(row.get("is_full_jd")):
        return "full_jd"
    if str(row.get("jd_text") or "").strip():
        return "partial_jd"
    return "snippet_only"


def _extract_section_lines(text: str, headings: list[str]) -> list[str]:
    if not text:
        return []

    lines = [_clean_line(line) for line in text.splitlines()]
    collected: list[str] = []
    in_section = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if in_section and collected:
                break
            continue

        matched_heading = _match_heading(line, headings)
        if matched_heading:
            in_section = True
            remainder = _extract_inline_remainder(line, matched_heading)
            if remainder:
                collected.append(remainder)
            continue

        if in_section and _match_heading(line, SECTION_BREAK_HEADINGS):
            break

        if in_section:
            collected.append(_strip_bullet(line))
            if len(collected) >= 6:
                break

    return _dedupe_preserve_order(collected)


def _extract_skills(text: str) -> list[str]:
    if not text:
        return []

    explicit_skills: list[str] = []
    skill_lines = _extract_section_lines(text, SKILL_LINE_HEADINGS)
    for line in skill_lines:
        for part in re.split(r"[,，/|；;]", line):
            normalized = _strip_bullet(part).strip()
            if normalized:
                explicit_skills.append(normalized)

    if explicit_skills:
        return _dedupe_preserve_order(explicit_skills)[:10]

    skills: list[str] = []
    text_lower = text.lower()
    for keyword in SKILL_KEYWORDS:
        if keyword.lower() in text_lower:
            skills.append(keyword)

    return _dedupe_preserve_order(skills)[:10]


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        values = value
    else:
        values = []
    return _dedupe_preserve_order([str(item).strip() for item in values if str(item).strip()])


def _match_heading(line: str, headings: list[str]) -> str | None:
    normalized = _clean_line(line).lower()
    for heading in headings:
        heading_lower = heading.lower()
        if normalized == heading_lower:
            return heading
        if normalized.startswith(f"{heading_lower}:") or normalized.startswith(f"{heading_lower}："):
            return heading
    return None


def _extract_inline_remainder(line: str, heading: str) -> str:
    normalized = _clean_line(line)
    remainder = normalized[len(heading) :].lstrip(":： ").strip()
    return _strip_bullet(remainder)


def _strip_bullet(value: str) -> str:
    return re.sub(r"^[\-\*\u2022\d\.\)\(]+\s*", "", value or "").strip()


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
