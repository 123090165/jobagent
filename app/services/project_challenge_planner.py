from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.schemas.match import MatchReport, RequirementMatch
from app.schemas.resume import ResumeProfile


class ChallengeRequirement(BaseModel):
    requirement: str
    match_level: str
    source: str | None = None
    related_resume_evidence: list[str] = Field(default_factory=list)
    reason_to_ask: str | None = None


def select_challenge_requirements(
    *,
    resume_profile: ResumeProfile,
    job_analysis,
    match_report: MatchReport,
    max_items: int = 6,
) -> list[ChallengeRequirement]:
    """Select small, evidence-aware requirements for project interview follow-up."""
    del job_analysis
    if max_items <= 0:
        return []

    selected: list[ChallengeRequirement] = []
    for match in sorted(match_report.requirement_matches, key=_requirement_priority):
        evidence = bind_resume_evidence_for_requirement(
            requirement=match.requirement,
            resume_profile=resume_profile,
            match_report=match_report,
        )
        if not _should_select_requirement(match, evidence):
            continue
        selected.append(
            ChallengeRequirement(
                requirement=match.requirement,
                match_level=match.match_level,
                source=match.category,
                related_resume_evidence=evidence,
                reason_to_ask=_reason_to_ask(match.match_level),
            )
        )
        if len(selected) >= max_items:
            break
    return selected


def bind_resume_evidence_for_requirement(
    *,
    requirement: str,
    resume_profile: ResumeProfile,
    match_report: MatchReport,
) -> list[str]:
    """Bind existing resume or match evidence to a requirement without inventing claims."""
    evidence: list[str] = []
    for match in match_report.requirement_matches:
        if _same_requirement(match.requirement, requirement) and match.resume_evidence:
            evidence.extend(match.resume_evidence)
            break

    if len(evidence) < 3:
        evidence.extend(_keyword_match_resume_evidence(requirement, resume_profile))

    return _dedupe([item for item in evidence if item.strip()])[:3]


def _should_select_requirement(match: RequirementMatch, evidence: list[str]) -> bool:
    if match.match_level == "missing":
        return match.importance in {"must", "should"} and _is_specific_requirement(match.requirement)
    if evidence:
        return True
    return _is_specific_requirement(match.requirement) and match.category in {"skill", "responsibility", "experience"}


def _requirement_priority(match: RequirementMatch) -> tuple[int, int, int]:
    match_priority = {"partial": 0, "matched": 1, "missing": 2}.get(match.match_level, 3)
    importance_priority = {"must": 0, "should": 1, "nice": 2}.get(match.importance, 3)
    source_priority = {"skill": 0, "experience": 1, "responsibility": 2, "keyword": 3}.get(match.category, 4)
    return (match_priority, importance_priority, source_priority)


def _keyword_match_resume_evidence(requirement: str, resume_profile: ResumeProfile) -> list[str]:
    tokens = _extract_keywords(requirement)
    if not tokens:
        return []

    evidence: list[str] = []
    for skill in resume_profile.skills:
        if _contains_any_token(skill, tokens):
            evidence.append(f"Skill: {skill}")

    for project in resume_profile.projects:
        parts = [project.name or "Project", project.description]
        if project.technologies:
            parts.append(f"Technologies: {', '.join(project.technologies)}")
        if project.highlights:
            parts.append(f"Highlights: {'; '.join(project.highlights)}")
        text = " | ".join(part.strip() for part in parts if part and part.strip())
        if text and _contains_any_token(text, tokens):
            evidence.append(f"Project: {text}")

    for experience in resume_profile.work_experiences:
        parts = [experience.role or "Work", experience.company or "", experience.description]
        if experience.technologies:
            parts.append(f"Technologies: {', '.join(experience.technologies)}")
        text = " | ".join(part.strip() for part in parts if part and part.strip())
        if text and _contains_any_token(text, tokens):
            evidence.append(f"Experience: {text}")

    return evidence


def _reason_to_ask(match_level: str) -> str:
    if match_level == "matched":
        return "Validate depth and authenticity for an already matched requirement."
    if match_level == "partial":
        return "Clarify the boundary of partially matched evidence."
    return "Handle an important JD gap honestly without inventing experience."


def _same_requirement(left: str, right: str) -> bool:
    return _normalize(left) == _normalize(right)


def _is_specific_requirement(requirement: str) -> bool:
    tokens = _extract_keywords(requirement)
    return bool(tokens) and len(requirement.strip()) >= 2


def _contains_any_token(text: str, tokens: list[str]) -> bool:
    normalized = _normalize(text)
    return any(token in normalized for token in tokens)


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9+.#/-]*", text.lower())
    filtered = [token for token in tokens if token not in _STOPWORDS]
    if filtered:
        return filtered[:6]
    normalized = _normalize(text)
    return [normalized] if normalized else []


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


_STOPWORDS = {
    "and",
    "or",
    "the",
    "a",
    "an",
    "to",
    "of",
    "in",
    "for",
    "with",
    "on",
    "using",
    "use",
    "build",
    "develop",
    "experience",
    "years",
}
