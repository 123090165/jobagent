from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from time import perf_counter
from typing import Protocol, cast

from app.repositories.rag_sync_repository import RAGSyncRepository, rag_sync_repository
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.schemas.chat import ChatCitation, ChatConversation, ChatSource
from app.schemas.knowledge import KnowledgeQueryResult
from app.schemas.rag_sync import RAGResourceType
from app.services.chat_context_builder import (
    ChatEvidence,
    apply_evidence_budget,
    build_chat_evidence,
)
from app.services.mcp import MCPClientError, resolve_modular_rag_service
from app.services.rag_query_expansion import expand_personal_knowledge_query


logger = logging.getLogger(__name__)

_SOURCE_TO_RESOURCE_TYPE: dict[ChatSource, str] = {
    "profile": "resume_profile",
    "saved_jobs": "saved_job",
}
_RESOURCE_TYPE_TO_SOURCE: dict[str, ChatSource] = {
    value: key for key, value in _SOURCE_TO_RESOURCE_TYPE.items()
}


class _AuthorizedKnowledgeService(Protocol):
    async def query_for_user(
        self,
        query: str,
        *,
        user_id: str,
        resource_types: tuple[str, ...],
        top_k: int,
        include_public: bool,
    ) -> KnowledgeQueryResult: ...


@dataclass(frozen=True)
class PersonalKnowledgeSearchOutcome:
    evidence: list[ChatEvidence]
    sources: list[ChatSource]
    warnings: list[str]
    service_available: bool
    timings_ms: dict[str, float] = field(default_factory=dict)


def build_chat_evidence_with_personal_knowledge(
    question: str,
    *,
    user_id: str,
    conversation: ChatConversation,
    requested_sources: list[ChatSource],
    active_refs: list[str],
    semantic_sources: list[ChatSource],
    personal_knowledge_requested: bool,
    personal_knowledge_query: str | None = None,
) -> tuple[list[ChatEvidence], list[str]]:
    database_evidence, warnings = build_chat_evidence(
        question,
        user_id=user_id,
        conversation=conversation,
        requested_sources=requested_sources,
        active_refs=active_refs,
    )
    personal_evidence: list[ChatEvidence] = []
    if personal_knowledge_requested:
        outcome = search_personal_knowledge(
            personal_knowledge_query or question,
            user_id=user_id,
            allowed_sources=semantic_sources,
        )
        personal_evidence = outcome.evidence
        warnings.extend(outcome.warnings)
        if not personal_evidence:
            fallback_sources = [
                source
                for source in semantic_sources
                if source not in requested_sources
            ]
            fallback_evidence, fallback_warnings = build_chat_evidence(
                question,
                user_id=user_id,
                conversation=conversation,
                requested_sources=fallback_sources,
                active_refs=[],
            )
            database_evidence.extend(fallback_evidence)
            warnings.extend(fallback_warnings)
            if fallback_sources:
                warnings.append("personal_knowledge_fallback:jobagent_database")
    evidence_by_citation = {
        item.citation.citation_id: item
        for item in [*database_evidence, *personal_evidence]
    }
    return (
        apply_evidence_budget(list(evidence_by_citation.values())),
        list(dict.fromkeys(warnings)),
    )


def search_personal_knowledge(
    question: str,
    *,
    user_id: str,
    allowed_sources: list[ChatSource],
    top_k: int = 6,
    service: _AuthorizedKnowledgeService | None = None,
    sync_repository: RAGSyncRepository = rag_sync_repository,
    profile_repository: ResumeProfileRepository = resume_profile_repository,
    job_repository: SavedJobRepository = saved_job_repository,
) -> PersonalKnowledgeSearchOutcome:
    started_at = perf_counter()
    resource_types = tuple(
        _SOURCE_TO_RESOURCE_TYPE[source]
        for source in dict.fromkeys(allowed_sources)
        if source in _SOURCE_TO_RESOURCE_TYPE
    )
    if not resource_types:
        return PersonalKnowledgeSearchOutcome([], [], [], True)

    try:
        resolved_service = service or resolve_modular_rag_service()
    except MCPClientError as exc:
        return _unavailable(exc, started_at=started_at)
    if resolved_service is None:
        return PersonalKnowledgeSearchOutcome(
            evidence=[],
            sources=[],
            warnings=["personal_knowledge_unavailable:not_configured"],
            service_available=False,
            timings_ms={"total": _elapsed_ms(started_at)},
        )

    expansion_started_at = perf_counter()
    expanded_query = expand_personal_knowledge_query(question)
    expansion_ms = _elapsed_ms(expansion_started_at)
    query_started_at = perf_counter()
    try:
        result = asyncio.run(
            resolved_service.query_for_user(
                expanded_query,
                user_id=user_id,
                resource_types=resource_types,
                top_k=max(1, min(10, top_k)),
                include_public=False,
            )
        )
    except (MCPClientError, RuntimeError) as exc:
        return _unavailable(
            exc,
            started_at=started_at,
            expansion_ms=expansion_ms,
            query_ms=_elapsed_ms(query_started_at),
        )
    query_ms = _elapsed_ms(query_started_at)

    hydration_started_at = perf_counter()
    evidence: list[ChatEvidence] = []
    sources: list[ChatSource] = []
    warnings: list[str] = []
    seen_resources: set[tuple[str, str]] = set()
    for match in result.results:
        metadata = match.metadata
        resource_type = str(metadata.get("resource_type", ""))
        resource_id = str(metadata.get("resource_id", ""))
        source = _RESOURCE_TYPE_TO_SOURCE.get(resource_type)
        if (
            source is None
            or source not in allowed_sources
            or not resource_id
            or metadata.get("owner_user_id") != user_id
            or metadata.get("visibility") != "private"
        ):
            warnings.append("personal_knowledge_result_rejected:scope")
            continue
        resource_key = (resource_type, resource_id)
        if resource_key in seen_resources:
            continue
        status = sync_repository.get_status(
            user_id=user_id,
            resource_type=cast(RAGResourceType, resource_type),
            resource_id=resource_id,
        )
        try:
            result_version = int(metadata.get("resource_version", 0))
        except (TypeError, ValueError):
            result_version = 0
        if (
            status is None
            or status.sync_status != "ready"
            or status.indexed_version != status.desired_version
            or result_version != status.indexed_version
            or metadata.get("document_id") != status.indexed_document_id
        ):
            warnings.append("personal_knowledge_result_rejected:stale")
            continue
        if resource_type == "resume_profile":
            profile = profile_repository.get(
                user_id=user_id,
                resume_profile_id=resource_id,
            )
            if profile is None or profile.archived_at is not None:
                warnings.append("personal_knowledge_result_rejected:stale")
                continue
            label = profile.name
            href = "/resume-profiles"
            current_content: dict[str, object] = {
                "name": profile.name,
                "summary": profile.summary,
                "target_roles": profile.target_roles,
                "target_directions": profile.target_directions,
                "core_skills": profile.core_skills,
                "supporting_skills": profile.supporting_skills,
                "preferred_locations": profile.preferred_locations,
                "work_arrangements": profile.work_arrangements,
                "strengths": profile.strengths,
                "risks": profile.risks,
            }
        else:
            job = job_repository.get(
                user_id=user_id,
                saved_job_id=resource_id,
            )
            if job is None or job.archived_at is not None:
                warnings.append("personal_knowledge_result_rejected:stale")
                continue
            analysis = job.latest_analysis
            label = f"{job.title} · {job.company or 'Unknown company'}"
            href = f"/saved-jobs/{resource_id}"
            current_content = {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "tags": job.tags,
                "notes": job.notes,
                "jd_excerpt": job.raw_jd_text[:1_400],
                "match_score": analysis.match_score if analysis else None,
                "recommendation": analysis.recommendation if analysis else None,
                "matched_strengths": analysis.matched_strengths if analysis else [],
                "critical_gaps": analysis.critical_gaps if analysis else [],
            }
        seen_resources.add(resource_key)
        sources.append(source)
        citation_id = (
            f"profile:{resource_id}"
            if resource_type == "resume_profile"
            else f"saved_job:{resource_id}"
        )
        evidence.append(
            ChatEvidence(
                citation=ChatCitation(
                    citation_id=citation_id,
                    source_type=source,
                    resource_id=resource_id,
                    label=label,
                    excerpt=match.text[:300],
                    href=href,
                ),
                content={
                    "retrieval_source": "modular_rag_mcp",
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "score": match.score,
                    "rag_excerpt": match.text[:1_200],
                    "current_resource": current_content,
                },
            )
        )
    if not evidence:
        warnings.append("personal_knowledge_no_usable_matches")
    timings_ms = {
        "query_expansion": expansion_ms,
        "mcp_query": query_ms,
        "hydrate_and_validate": _elapsed_ms(hydration_started_at),
        "total": _elapsed_ms(started_at),
    }
    logger.info(
        "personal_knowledge_search available=true matches=%d evidence=%d "
        "query_expansion_ms=%.3f mcp_query_ms=%.3f hydrate_and_validate_ms=%.3f "
        "total_ms=%.3f",
        len(result.results),
        len(evidence),
        timings_ms["query_expansion"],
        timings_ms["mcp_query"],
        timings_ms["hydrate_and_validate"],
        timings_ms["total"],
    )
    return PersonalKnowledgeSearchOutcome(
        evidence=evidence,
        sources=list(dict.fromkeys(sources)),
        warnings=list(dict.fromkeys(warnings)),
        service_available=True,
        timings_ms=timings_ms,
    )


def _unavailable(
    exc: Exception,
    *,
    started_at: float,
    expansion_ms: float | None = None,
    query_ms: float | None = None,
) -> PersonalKnowledgeSearchOutcome:
    timings_ms = {"total": _elapsed_ms(started_at)}
    if expansion_ms is not None:
        timings_ms["query_expansion"] = expansion_ms
    if query_ms is not None:
        timings_ms["mcp_query"] = query_ms
    logger.info(
        "personal_knowledge_search available=false error=%s total_ms=%.3f",
        type(exc).__name__,
        timings_ms["total"],
    )
    return PersonalKnowledgeSearchOutcome(
        evidence=[],
        sources=[],
        warnings=[f"personal_knowledge_unavailable:{type(exc).__name__}"],
        service_available=False,
        timings_ms=timings_ms,
    )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1_000, 3)
