from __future__ import annotations

import re

from app.schemas.job import JDRequirement

_REQUIRED_MARKERS = ("require", "must", "need to", "必须", "要求", "需具备")
_PREFERRED_MARKERS = ("preferred", "plus", "nice to have", "bonus", "优先", "加分")


def build_legacy_requirements(
    *,
    raw_jd: str,
    required_skills: list[str],
    preferred_skills: list[str],
    experience_requirements: list[str],
    education_requirements: list[str],
) -> list[JDRequirement]:
    requirements: list[JDRequirement] = []
    requirements.extend(
        _requirement(raw_jd, "skill", skill, "required")
        for skill in required_skills
    )
    requirements.extend(
        _requirement(raw_jd, "skill", skill, "preferred")
        for skill in preferred_skills
    )
    requirements.extend(
        _requirement(raw_jd, "experience", item, "required")
        for item in experience_requirements
    )
    requirements.extend(
        _requirement(raw_jd, "education", item, "required")
        for item in education_requirements
    )
    return _dedupe_requirements(requirements)


def ground_requirements(
    raw_jd: str,
    requirements: list[JDRequirement],
) -> list[JDRequirement]:
    grounded: list[JDRequirement] = []
    for requirement in requirements:
        quote = requirement.evidence_quote
        if not quote or not _contains_normalized(raw_jd, quote):
            quote = find_evidence_quote(raw_jd, requirement.name)
        confidence = requirement.confidence if quote else min(requirement.confidence, 0.5)
        grounded.append(
            requirement.model_copy(
                update={"evidence_quote": quote, "confidence": confidence}
            )
        )
    return _dedupe_requirements(grounded)


def find_evidence_quote(raw_jd: str, term: str) -> str | None:
    normalized_term = " ".join(term.split()).casefold()
    if not normalized_term:
        return None
    for segment in _segments(raw_jd):
        if normalized_term in " ".join(segment.split()).casefold():
            return segment.strip()[:500]
    return None


def _requirement(
    raw_jd: str,
    category: str,
    name: str,
    default_necessity: str,
) -> JDRequirement:
    quote = find_evidence_quote(raw_jd, name)
    necessity = _necessity_from_quote(quote, default=default_necessity)
    return JDRequirement.model_validate(
        {
            "category": category,
            "name": name,
            "necessity": necessity,
            "evidence_quote": quote,
            "confidence": 0.9 if quote else 0.5,
        }
    )


def _necessity_from_quote(quote: str | None, *, default: str) -> str:
    if not quote:
        return "unknown"
    normalized = quote.casefold()
    if any(marker in normalized for marker in _PREFERRED_MARKERS):
        return "preferred"
    if any(marker in normalized for marker in _REQUIRED_MARKERS):
        return "required"
    return default


def _segments(raw_jd: str) -> list[str]:
    return [
        segment.strip()
        for segment in re.split(r"(?:\r?\n)+|(?<=[.!?。！？；;])\s*", raw_jd)
        if segment.strip()
    ]


def _contains_normalized(text: str, fragment: str) -> bool:
    return " ".join(fragment.split()).casefold() in " ".join(text.split()).casefold()


def _dedupe_requirements(requirements: list[JDRequirement]) -> list[JDRequirement]:
    deduped: list[JDRequirement] = []
    seen: set[tuple[str, str, str]] = set()
    for requirement in requirements:
        key = (
            requirement.category,
            requirement.name.strip().casefold(),
            requirement.necessity,
        )
        if not requirement.name.strip() or key in seen:
            continue
        seen.add(key)
        deduped.append(requirement)
    return deduped
