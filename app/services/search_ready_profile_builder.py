"""把确认画像压缩成搜索阶段使用的角色、技能、地点和证据摘要。"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.resume import ResumeProfile
from app.schemas.search_ready_profile import SearchReadyProfile

QICHACHA = "\u4f01\u67e5\u67e5"

CATEGORY_CORE_SKILLS: dict[str, list[str]] = {
    "ai_agent_backend": [
        "AI Agent",
        "FastAPI",
        "LangGraph",
        "LangChain",
        "backend API",
        "evaluation / testing",
    ],
    "ai_health": [
        "AI health algorithm",
        "physiological signal processing",
        "PPG",
        "ECG",
        "ACC",
        "wearable health monitoring",
        "health analytics",
        "feature extraction",
        "signal segmentation",
    ],
    "ml_audio": [
        "audio classification",
        "ASR",
        "MFCC",
        "STFT",
        "CNN",
        "model evaluation",
        "error analysis",
    ],
    "business_fa": [
        "industry research",
        "market research",
        "competitor analysis",
        "investment analysis",
        "FA project support",
        "CRM tracking",
        "meeting notes",
    ],
    "embedded": [
        "STM32 development",
        "embedded C",
        "UART / USART",
        "GPIO",
        "DMA",
        "ADC",
        "PWM",
    ],
}

CATEGORY_AUXILIARY_SKILLS: dict[str, list[str]] = {
    "ai_agent_backend": ["Python", "Streamlit", "SQLite", "Pydantic", "Git"],
    "ai_health": [
        "Python",
        "MATLAB",
        "PyTorch",
        "TensorFlow",
        "NumPy",
        "Pandas",
        "SciPy",
        "Matplotlib",
    ],
    "ml_audio": ["Python", "PyTorch", "Librosa", "NumPy", "Pandas"],
    "business_fa": ["Wind", QICHACHA, "Excel", "PowerPoint", "CRM"],
    "embedded": ["C", "C++", "Keil", "CubeMX", "Git"],
}

CATEGORY_SEARCH_KEYWORDS: dict[str, list[str]] = {
    "ai_agent_backend": [
        "AI Agent",
        "Backend Engineer",
        "LLM application",
        "backend API",
        "resume parsing",
        "job matching",
        "evaluation",
    ],
    "ai_health": [
        "AI health algorithm",
        "physiological signal processing",
        "PPG",
        "ECG",
        "ACC",
        "wearable health monitoring",
        "blood oxygen",
        "heart rate",
        "blood pressure",
        "biosignal",
        "health analytics",
    ],
    "ml_audio": [
        "audio classification",
        "ASR",
        "MFCC",
        "STFT",
        "CNN",
        "validation accuracy",
        "error analysis",
    ],
    "business_fa": [
        "Business Analyst",
        "Investment Analyst",
        "FA Intern",
        "industry research",
        "market research",
        "competitor analysis",
        "Wind",
        QICHACHA,
        "CRM",
        "Excel",
        "PowerPoint",
        "meeting notes",
    ],
    "embedded": [
        "Embedded Software Engineer",
        "STM32",
        "UART",
        "USART",
        "GPIO",
        "DMA",
        "ADC",
        "PWM",
    ],
}

LOCATION_PATTERNS: dict[str, list[str]] = {
    "Shenzhen": ["shenzhen", "娣卞湷"],
    "Hong Kong": ["hong kong", "棣欐腐"],
    "Hangzhou": ["hangzhou", "鏉窞"],
    "Tokyo": ["tokyo", "涓滀含"],
}

WORK_ARRANGEMENT_PATTERNS: dict[str, list[str]] = {
    "internship": ["intern", "internship", "瀹炰範"],
    "full-time": ["full-time", "full time", "鍏ㄨ亴"],
    "remote": ["remote", "杩滅▼"],
    "onsite": ["onsite", "on-site", "鐜板満"],
    "hybrid": ["hybrid", "娣峰悎鍔炲叕"],
}

TEXT_NORMALIZATION_MAP: dict[str, str] = {
    "浼佹煡鏌?": QICHACHA,
    "浼佹煡鏌�": QICHACHA,
    "qichacha": QICHACHA,
}


def build_search_ready_profile(
    parsed_profile: ResumeProfile,
    target_roles: list[str] | None = None,
    *,
    quality_warnings: list[str] | None = None,
    missing_info_questions: list[str] | None = None,
    source_profile_snapshot: dict[str, Any] | None = None,
) -> SearchReadyProfile:
    normalized_roles = _dedupe(target_roles or [])
    evidence_text = _build_evidence_text(parsed_profile, normalized_roles)
    categories = _detect_categories(parsed_profile, normalized_roles, evidence_text)

    target_directions = _build_target_directions(parsed_profile, normalized_roles, categories)
    core_skills = _build_core_skills(parsed_profile, categories, evidence_text)
    auxiliary_skills = _build_auxiliary_skills(parsed_profile, categories, core_skills)
    search_keywords = _build_search_keywords(
        parsed_profile,
        target_directions,
        core_skills,
        auxiliary_skills,
        categories,
    )
    preferred_locations = _extract_preferred_locations(parsed_profile.raw_text)
    work_arrangements = _extract_work_arrangements(parsed_profile.raw_text, target_directions)
    company_preferences = _extract_company_preferences(parsed_profile.raw_text)
    profile_notes = _build_profile_notes(
        parsed_profile,
        categories,
        target_directions,
        preferred_locations,
        quality_warnings or [],
    )
    summary = _build_summary(
        parsed_profile,
        target_directions,
        core_skills,
        preferred_locations,
        quality_warnings or [],
    )

    return SearchReadyProfile(
        summary=summary,
        target_directions=target_directions,
        core_skills=core_skills,
        auxiliary_skills=auxiliary_skills,
        search_keywords=search_keywords,
        preferred_locations=preferred_locations,
        work_arrangements=work_arrangements,
        company_preferences=company_preferences,
        profile_notes=profile_notes,
        quality_warnings=list(quality_warnings or []),
        missing_info_questions=list(missing_info_questions or []),
        source_profile_snapshot=source_profile_snapshot or parsed_profile.model_dump(mode="json"),
    )


def _build_target_directions(
    parsed_profile: ResumeProfile,
    normalized_roles: list[str],
    categories: list[str],
) -> list[str]:
    if normalized_roles:
        return normalized_roles

    if _is_weak_profile(parsed_profile):
        return []

    inferred: list[str] = []
    if "ai_health" in categories:
        inferred.extend(
            [
                "AI Health Algorithm Intern",
                "Physiological Signal Processing Intern",
            ]
        )
    if "ml_audio" in categories:
        inferred.extend(["Machine Learning Engineer", "AI Engineer"])
    if "business_fa" in categories:
        inferred.extend(["Business Analyst", "Investment Analyst"])
    if "ai_agent_backend" in categories:
        inferred.extend(["AI Agent Engineer", "Backend Engineer"])
    if "embedded" in categories:
        inferred.append("Embedded Software Engineer")
    return _dedupe(inferred)


def _build_core_skills(
    parsed_profile: ResumeProfile,
    categories: list[str],
    evidence_text: str,
) -> list[str]:
    core_skills: list[str] = []
    for category in categories:
        for skill in CATEGORY_CORE_SKILLS.get(category, []):
            if _supports_term(skill, parsed_profile, evidence_text, category):
                core_skills.append(skill)
    return _dedupe(core_skills)


def _build_auxiliary_skills(
    parsed_profile: ResumeProfile,
    categories: list[str],
    core_skills: list[str],
) -> list[str]:
    auxiliary: list[str] = []
    for category in categories:
        auxiliary.extend(CATEGORY_AUXILIARY_SKILLS.get(category, []))

    parsed_skill_map = {
        _normalized_key(skill): _normalize_display_term(skill) for skill in parsed_profile.skills
    }
    core_skill_keys = {_normalized_key(skill) for skill in core_skills}
    normalized_raw_text = _normalize_text(parsed_profile.raw_text).lower()
    final_auxiliary: list[str] = []
    for skill in auxiliary:
        normalized_skill = _normalize_display_term(skill)
        skill_key = _normalized_key(normalized_skill)
        if skill_key in core_skill_keys:
            continue
        if skill_key in parsed_skill_map:
            final_auxiliary.append(parsed_skill_map[skill_key])
            continue
        if normalized_skill in {"SciPy", "Matplotlib"} and normalized_skill.lower() in normalized_raw_text:
            final_auxiliary.append(normalized_skill)
            continue
        if normalized_skill == QICHACHA and QICHACHA in normalized_raw_text:
            final_auxiliary.append(normalized_skill)
            continue
        if normalized_skill in {"Wind", "Excel", "PowerPoint", "CRM"} and normalized_skill.lower() in normalized_raw_text:
            final_auxiliary.append(normalized_skill)
    return _dedupe(final_auxiliary)


def _build_search_keywords(
    parsed_profile: ResumeProfile,
    target_directions: list[str],
    core_skills: list[str],
    auxiliary_skills: list[str],
    categories: list[str],
) -> list[str]:
    keywords: list[str] = []
    keywords.extend(target_directions)
    keywords.extend(core_skills)
    keywords.extend(auxiliary_skills)
    for category in categories:
        keywords.extend(CATEGORY_SEARCH_KEYWORDS.get(category, []))
    if parsed_profile.skills and len(target_directions) <= 3:
        keywords.extend(parsed_profile.skills[:8])
    return _dedupe(keywords)


def _extract_preferred_locations(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for canonical, patterns in LOCATION_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            found.append(canonical)
    return found


def _extract_work_arrangements(text: str, target_directions: list[str]) -> list[str]:
    lowered = text.lower()
    arrangements: list[str] = []
    for arrangement, patterns in WORK_ARRANGEMENT_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            arrangements.append(arrangement)
    if any("intern" in role.lower() for role in target_directions):
        arrangements.append("internship")
    return _dedupe(arrangements)


def _extract_company_preferences(text: str) -> list[str]:
    preferences: list[str] = []
    lowered = text.lower()
    if "wearable" in lowered:
        preferences.append("wearable health")
    if "biomedical" in lowered:
        preferences.append("biomedical AI")
    return preferences


def _build_profile_notes(
    parsed_profile: ResumeProfile,
    categories: list[str],
    target_directions: list[str],
    preferred_locations: list[str],
    quality_warnings: list[str],
) -> list[str]:
    notes: list[str] = []
    if preferred_locations:
        notes.append(f"Location preference: {', '.join(preferred_locations)}.")
    if parsed_profile.work_experiences and len(parsed_profile.work_experiences) <= 1:
        notes.append("Profile relies more on project evidence than formal work experience.")
    if not parsed_profile.work_experiences:
        notes.append("Project-heavy profile with limited formal work experience evidence.")
    if "ai_health" in categories:
        notes.append("Profile is oriented toward wearable health, biosignal, and AI health algorithm search.")
    if "business_fa" in categories:
        notes.append("Profile is oriented toward research-heavy business, investment, and FA support search.")
    if not target_directions:
        notes.append("Target directions still need explicit user confirmation.")
    if quality_warnings:
        notes.append(f"Open quality follow-up: {quality_warnings[0]}.")
    return _dedupe(notes)


def _build_summary(
    parsed_profile: ResumeProfile,
    target_directions: list[str],
    core_skills: list[str],
    preferred_locations: list[str],
    quality_warnings: list[str],
) -> str:
    if not target_directions and _is_weak_profile(parsed_profile):
        return (
            "Profile information is limited and still needs target-direction confirmation. "
            "Current evidence mainly points to a small Python-related starting point."
        )

    direction_text = ", ".join(target_directions[:3]) if target_directions else "search-ready roles"
    core_text = ", ".join(core_skills[:4]) if core_skills else "transferable project evidence"
    summary = f"Search-ready profile aligned to {direction_text}, with core evidence around {core_text}."
    if preferred_locations:
        summary += f" Preferred locations include {', '.join(preferred_locations)}."
    elif quality_warnings:
        summary += " Some search fields still need confirmation before broad job targeting."
    return summary


def _detect_categories(
    parsed_profile: ResumeProfile,
    normalized_roles: list[str],
    evidence_text: str,
) -> list[str]:
    categories: list[str] = []
    lowered_roles = " ".join(normalized_roles).lower()
    lowered_evidence = _normalize_text(evidence_text).lower()

    if any(
        term in lowered_roles or term in lowered_evidence
        for term in [
            "ai health",
            "physiological",
            "biomedical",
            "ppg",
            "ecg",
            "wearable",
        ]
    ):
        categories.append("ai_health")
    if any(
        term in lowered_roles or term in lowered_evidence
        for term in ["audio", "asr", "mfcc", "stft", "librosa", "speech"]
    ):
        categories.append("ml_audio")
    if (
        "business analyst" in lowered_roles
        or "investment analyst" in lowered_roles
        or "fa intern" in lowered_roles
        or "wind" in lowered_evidence
        or "crm" in lowered_evidence
        or QICHACHA.lower() in lowered_evidence
        or re.search(r"\bfa\b", lowered_evidence)
    ):
        categories.append("business_fa")
    if any(
        term in lowered_roles or term in lowered_evidence
        for term in ["ai agent", "backend", "fastapi", "langgraph", "langchain"]
    ):
        categories.append("ai_agent_backend")
    if any(
        term in lowered_roles or term in lowered_evidence
        for term in ["embedded", "stm32", "uart", "usart", "dma", "adc", "pwm"]
    ):
        categories.append("embedded")

    return _dedupe(categories)


def _supports_term(
    term: str,
    parsed_profile: ResumeProfile,
    evidence_text: str,
    category: str,
) -> bool:
    lowered = _normalize_text(evidence_text).lower()
    direct_markers = {
        "AI Agent": ["ai agent", "agent"],
        "backend API": ["fastapi", "api", "backend"],
        "evaluation / testing": ["evaluation", "tests", "pytest", "accuracy"],
        "AI health algorithm": ["ai health", "health analytics", "wearable"],
        "model evaluation": ["accuracy", "confusion matrix", "error analysis", "evaluation"],
        "FA project support": ["deal memo", "peer mapping", "fa intern", "fa team", "horizon capital"],
        "CRM tracking": ["crm"],
        "industry research": ["industry research", "research-heavy", "研究", "行业研究"],
        "market research": ["market research", "market size", "市场", "商业模式"],
        "competitor analysis": ["competitor analysis", "competitive landscape", "竞品", "竞争格局"],
        "meeting notes": ["meeting notes", "investor meeting notes", "纪要", "会议纪要"],
        "embedded C": ["c/c++", "embedded c", "stm32"],
        "UART / USART": ["uart", "usart"],
        "STM32 development": ["stm32"],
    }
    if term in direct_markers:
        return any(marker in lowered for marker in direct_markers[term])
    if term.lower() in lowered:
        return True
    if category == "business_fa" and term == "investment analysis":
        return "investment" in lowered or "融资" in lowered or "投资" in lowered
    if category == "ai_health" and term in {"feature extraction", "signal segmentation"}:
        return term.lower() in lowered
    return False


def _build_evidence_text(parsed_profile: ResumeProfile, target_roles: list[str]) -> str:
    items: list[str] = [parsed_profile.raw_text, *target_roles, *parsed_profile.skills]
    items.extend(project.raw_text for project in parsed_profile.projects)
    items.extend(work.raw_text for work in parsed_profile.work_experiences)
    items.extend(education.raw_text for education in parsed_profile.education)
    items.extend(parsed_profile.highlights)
    return "\n".join(item for item in items if item)


def _is_weak_profile(parsed_profile: ResumeProfile) -> bool:
    return (
        len(parsed_profile.skills) <= 1
        and len(parsed_profile.projects) <= 1
        and not parsed_profile.work_experiences
        and len(parsed_profile.highlights) == 0
    )


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_display_term(item)
        key = _normalized_key(normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _normalize_text(text: str) -> str:
    normalized = text
    for bad, good in TEXT_NORMALIZATION_MAP.items():
        normalized = normalized.replace(bad, good)
    return normalized


def _normalize_display_term(term: str) -> str:
    return _normalize_text(term).strip()


def _normalized_key(term: str) -> str:
    return _normalize_display_term(term).lower()
