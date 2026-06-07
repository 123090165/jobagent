from __future__ import annotations

import re

from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, RequirementMatch
from app.schemas.resume import ResumeProfile
from app.agents.types import AgentRunMetadata, AgentRunResult


def analyze_match(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> MatchReport:
    """Compare a structured resume and JD analysis."""
    return run_match_agent(resume_profile, job_analysis).output


def run_match_agent(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> AgentRunResult[MatchReport]:
    """Compare a structured resume and JD analysis with metadata."""
    from app.services.mock_pipeline import mock_match_analysis

    report = mock_match_analysis(resume_profile, job_analysis)
    report = report.model_copy(
        update={
            "requirement_matches": _build_requirement_matches(
                resume_profile,
                job_analysis,
            )
        }
    )

    return AgentRunResult(
        output=report,
        metadata=AgentRunMetadata(
            agent_name="MatchAgent",
            mode="mock",
            guardrails=[
                "匹配分必须有证据",
                "缺失项必须来自 JD 和简历差距",
            ],
        ),
    )


def _build_requirement_matches(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> list[RequirementMatch]:
    requirement_candidates = _collect_requirement_candidates(job_analysis)
    if not requirement_candidates:
        return []

    resume_evidence_pool = _collect_resume_evidence(resume_profile)
    matches: list[RequirementMatch] = []
    for requirement, category, importance in requirement_candidates[:10]:
        matches.append(
            _match_requirement(
                requirement=requirement,
                category=category,
                importance=importance,
                resume_evidence_pool=resume_evidence_pool,
            )
        )
    return matches


def _collect_requirement_candidates(job_analysis: JobAnalysis) -> list[tuple[str, str, str]]:
    candidates: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    source_groups = [
        (job_analysis.required_skills, "skill", "must"),
        (job_analysis.experience_requirements, "experience", "must"),
        (job_analysis.education_requirements, "education", "must"),
        (job_analysis.responsibilities, "responsibility", "should"),
        (job_analysis.implicit_requirements, "general", "should"),
        (job_analysis.preferred_skills, "skill", "nice"),
        (job_analysis.keywords, "keyword", "must"),
    ]
    for values, category, importance in source_groups:
        for value in values:
            normalized_value = _normalize_text(value)
            if not normalized_value or normalized_value in seen:
                continue
            seen.add(normalized_value)
            candidates.append((value.strip(), category, importance))
            if len(candidates) >= 10:
                return candidates
    return candidates


def _collect_resume_evidence(resume_profile: ResumeProfile) -> list[tuple[str, str]]:
    evidence: list[tuple[str, str]] = []
    for skill in resume_profile.skills:
        if skill.strip():
            evidence.append(("skill", f"Skill: {skill.strip()}"))
    for project in resume_profile.projects:
        parts = [project.name or "Project", project.description]
        if project.technologies:
            parts.append(f"Technologies: {', '.join(project.technologies)}")
        if project.highlights:
            parts.append(f"Highlights: {'; '.join(project.highlights)}")
        evidence.append(("project", " | ".join(part.strip() for part in parts if part.strip())))
    for experience in resume_profile.work_experiences:
        parts = [experience.role or "Work", experience.company or "", experience.description]
        if experience.technologies:
            parts.append(f"Technologies: {', '.join(experience.technologies)}")
        evidence.append(("experience", " | ".join(part.strip() for part in parts if part.strip())))
    for highlight in resume_profile.highlights:
        if highlight.strip():
            evidence.append(("highlight", f"Highlight: {highlight.strip()}"))
    for certificate in resume_profile.certificates:
        if certificate.strip():
            evidence.append(("certificate", f"Certificate: {certificate.strip()}"))
    for education in resume_profile.education:
        if education.raw_text.strip():
            evidence.append(("education", f"Education: {education.raw_text.strip()}"))
    return evidence


def _match_requirement(
    *,
    requirement: str,
    category: str,
    importance: str,
    resume_evidence_pool: list[tuple[str, str]],
) -> RequirementMatch:
    normalized_requirement = _normalize_text(requirement)
    requirement_tokens = _extract_keywords(requirement)
    direct_hits: list[str] = []
    partial_hits: list[str] = []

    for _, evidence_text in resume_evidence_pool:
        normalized_evidence = _normalize_text(evidence_text)
        if not normalized_evidence:
            continue
        if _is_direct_match(normalized_requirement, requirement_tokens, normalized_evidence):
            direct_hits.append(evidence_text)
            continue
        overlap_count = _count_overlap(requirement_tokens, normalized_evidence)
        if overlap_count > 0:
            partial_hits.append(evidence_text)

    if direct_hits:
        return RequirementMatch(
            requirement=requirement,
            category=category,
            importance=importance,
            match_level="matched",
            resume_evidence=_dedupe_items(direct_hits)[:3],
        )

    if partial_hits:
        return RequirementMatch(
            requirement=requirement,
            category=category,
            importance=importance,
            match_level="partial",
            resume_evidence=_dedupe_items(partial_hits)[:3],
            gap_reason=_build_gap_reason(requirement, category, partial=True),
            improvement_hint=_build_improvement_hint(requirement, category, partial=True),
        )

    return RequirementMatch(
        requirement=requirement,
        category=category,
        importance=importance,
        match_level="missing",
        gap_reason=_build_gap_reason(requirement, category, partial=False),
        improvement_hint=_build_improvement_hint(requirement, category, partial=False),
    )


def _is_direct_match(
    normalized_requirement: str,
    requirement_tokens: list[str],
    normalized_evidence: str,
) -> bool:
    if normalized_requirement and normalized_requirement in normalized_evidence:
        return True
    if not requirement_tokens:
        return False
    return all(token in normalized_evidence for token in requirement_tokens)


def _count_overlap(requirement_tokens: list[str], normalized_evidence: str) -> int:
    return sum(1 for token in requirement_tokens if token in normalized_evidence)


def _build_gap_reason(requirement: str, category: str, *, partial: bool) -> str:
    if partial:
        return f"Resume mentions related evidence for {requirement}, but coverage is still incomplete."
    if category == "responsibility":
        return f"Resume does not show a clear delivery example for {requirement}."
    if category == "experience":
        return f"Resume does not show enough prior experience aligned with {requirement}."
    return f"Resume does not show clear evidence for {requirement}."


def _build_improvement_hint(requirement: str, category: str, *, partial: bool) -> str:
    if category == "responsibility":
        return f"Add one project or work bullet that shows how you handled {requirement}."
    if category == "experience":
        return f"Describe a concrete project or work example that demonstrates {requirement}."
    if partial:
        return f"Make {requirement} explicit in a project or work bullet with outcome evidence."
    return f"Add truthful project, work, or skills evidence that demonstrates {requirement}."


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9+.#/-]*", text.lower())
    filtered = [token for token in tokens if token not in _STOPWORDS]
    if filtered:
        return filtered[:5]
    normalized_text = _normalize_text(text)
    return [normalized_text] if normalized_text else []


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _dedupe_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        results.append(item)
    return results


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
