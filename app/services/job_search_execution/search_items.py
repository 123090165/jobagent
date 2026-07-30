from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.schemas.job_search import (
    JobSearchCandidateSnapshot,
    JobSearchItem,
    JobSearchItemStage,
    JobSearchResult,
)
from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_recall_metrics import candidate_recall_key


def build_search_items(
    run_id: str,
    candidates: list[RawJobCandidate],
    *,
    stage: JobSearchItemStage,
    results: list[JobSearchResult] | None = None,
) -> list[JobSearchItem]:
    now = datetime.now(timezone.utc)
    results_by_key = {
        candidate_recall_key(result): result
        for result in (results or [])
    }
    items: list[JobSearchItem] = []
    for rank, candidate in enumerate(candidates, start=1):
        stable_key = candidate_recall_key(candidate)
        result = results_by_key.get(stable_key)
        effective_stage: JobSearchItemStage = "final" if result is not None else stage
        items.append(
            JobSearchItem(
                job_search_item_id=str(
                    uuid5(NAMESPACE_URL, f"job-search-item:{run_id}:{stable_key}")
                ),
                job_search_run_id=run_id,
                stable_candidate_key=stable_key,
                rank=rank,
                stage=effective_stage,
                candidate=JobSearchCandidateSnapshot(
                    title=candidate.title or "Untitled role",
                    company=candidate.company,
                    location=candidate.location,
                    source_provider=candidate.source_provider,
                    source_url=candidate.source_url,
                    snippet=candidate.snippet,
                    raw_description=candidate.raw_description,
                    discovery_query=candidate.discovery_query,
                    discovery_rank=candidate.discovery_rank,
                    detail_status=candidate.detail_status,
                    provider_warnings=candidate.provider_warnings,
                ),
                result=result,
                created_at=now,
                updated_at=now,
            )
        )
    return items
