from __future__ import annotations

import re

from app.schemas.profile_enrichment import EvidenceBoundSuggestion

VALID_CONFIDENCE_LABELS = {"strong", "medium", "limited", "weak"}
SKILL_FIELDS = {
    "skill",
    "skills",
    "technical_stack",
    "technologies",
    "technology",
}
ENTITY_FIELDS = {
    "company",
    "school",
    "project_name",
    "award",
    "certificate",
    "lab",
}
SKILL_NORMALIZATIONS = {
    "rest api": ["restful api", "restful apis", "rest api", "rest apis"],
    "rest apis": ["restful api", "restful apis", "rest api", "rest apis"],
}
QUANTIFIED_CLAIM_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ms|s|k|m|apis?|tests?|users?|x|gb|mb)?\b",
    re.IGNORECASE,
)


def validate_evidence_bound_suggestion(
    *,
    suggestion: EvidenceBoundSuggestion,
    source_text: str,
    full_resume_text: str,
    known_skills: list[str] | None = None,
) -> EvidenceBoundSuggestion | None:
    """Keep only suggestions grounded in parser evidence or the source resume."""
    if not _has_required_fields(suggestion):
        return None

    source_quote = suggestion.source_quote.strip()
    evidence_text = f"{source_text}\n{full_resume_text}"
    if source_quote not in source_text and source_quote not in full_resume_text:
        return None

    value_text = _suggested_value_text(suggestion.suggested_value)
    if not value_text:
        return None

    if _has_unsupported_quantified_claim(value_text, source_quote, evidence_text):
        return None

    field_name = suggestion.field.strip().lower()
    if field_name in SKILL_FIELDS and _has_unsupported_skill(
        value_text=value_text,
        source_quote=source_quote,
        evidence_text=evidence_text,
        known_skills=known_skills or [],
    ):
        return None

    if field_name in ENTITY_FIELDS and not _value_terms_are_grounded(
        value_text,
        source_quote,
        evidence_text,
    ):
        return None

    return suggestion.model_copy(
        update={
            "source_quote": source_quote,
            "confidence_label": suggestion.confidence_label.strip().lower(),
        }
    )


def _has_required_fields(suggestion: EvidenceBoundSuggestion) -> bool:
    if not suggestion.section.strip():
        return False
    if not suggestion.field.strip():
        return False
    if not suggestion.source_quote.strip():
        return False
    if suggestion.confidence_label.strip().lower() not in VALID_CONFIDENCE_LABELS:
        return False
    return bool(_suggested_value_text(suggestion.suggested_value))


def _suggested_value_text(value: str | list[str]) -> str:
    if isinstance(value, str):
        return value.strip()
    return " ".join(item.strip() for item in value if item.strip()).strip()


def _has_unsupported_quantified_claim(
    value_text: str,
    source_quote: str,
    evidence_text: str,
) -> bool:
    source_lower = source_quote.lower()
    evidence_lower = evidence_text.lower()
    for match in QUANTIFIED_CLAIM_RE.findall(value_text):
        normalized = match.strip().lower()
        if not normalized:
            continue
        compact = normalized.replace(" ", "")
        if (
            normalized not in source_lower
            and normalized not in evidence_lower
            and compact not in source_lower.replace(" ", "")
            and compact not in evidence_lower.replace(" ", "")
        ):
            return True
    return False


def _has_unsupported_skill(
    *,
    value_text: str,
    source_quote: str,
    evidence_text: str,
    known_skills: list[str],
) -> bool:
    evidence_lower = evidence_text.lower()
    quote_lower = source_quote.lower()
    for skill in _split_value_terms(value_text):
        skill_lower = skill.lower()
        if _term_is_grounded(skill_lower, quote_lower, evidence_lower):
            continue
        if any(_normalization_is_grounded(skill_lower, quote_lower, evidence_lower)):
            continue
        if any(
            known_skill.lower() == skill_lower
            and known_skill.lower() in evidence_lower
            for known_skill in known_skills
        ):
            continue
        return True
    return False


def _value_terms_are_grounded(
    value_text: str,
    source_quote: str,
    evidence_text: str,
) -> bool:
    quote_lower = source_quote.lower()
    evidence_lower = evidence_text.lower()
    terms = _split_value_terms(value_text)
    return bool(terms) and all(
        _term_is_grounded(term.lower(), quote_lower, evidence_lower)
        for term in terms
    )


def _term_is_grounded(term: str, quote_lower: str, evidence_lower: str) -> bool:
    return term in quote_lower or term in evidence_lower


def _normalization_is_grounded(
    skill_lower: str,
    quote_lower: str,
    evidence_lower: str,
) -> list[bool]:
    aliases = SKILL_NORMALIZATIONS.get(skill_lower, [])
    grounded_aliases = [
        alias in quote_lower or alias in evidence_lower for alias in aliases
    ]
    if not grounded_aliases:
        compact = skill_lower.replace("-", " ").replace("_", " ")
        grounded_aliases.append(compact in quote_lower or compact in evidence_lower)
    return grounded_aliases


def _split_value_terms(value_text: str) -> list[str]:
    normalized = value_text.replace("/", ",").replace(";", ",")
    if "," in normalized:
        raw_terms = normalized.split(",")
    else:
        raw_terms = [normalized]
    return [term.strip(" .:-") for term in raw_terms if term.strip(" .:-")]
