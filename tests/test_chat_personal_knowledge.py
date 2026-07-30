"""回归验证Assistant 会话、消息与上下文的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from types import SimpleNamespace

from app.schemas.knowledge import KnowledgeMatch, KnowledgeQueryResult
from app.services.chat_personal_knowledge import search_personal_knowledge


class _KnowledgeService:
    def __init__(self, results: list[KnowledgeMatch]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def query_for_user(self, query: str, **kwargs) -> KnowledgeQueryResult:
        self.calls.append({"query": query, **kwargs})
        return KnowledgeQueryResult(results=self.results)


class _StatusRepository:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready

    def get_status(self, **kwargs):
        return SimpleNamespace(
            sync_status="ready" if self.ready else "pending",
            indexed_version=2 if self.ready else 1,
            desired_version=2,
            indexed_document_id="document-1",
        )


class _ProfileRepository:
    def get(self, **kwargs):
        return None


class _JobRepository:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available

    def get(self, *, user_id: str, saved_job_id: str):
        if not self.available or user_id != "user-1":
            return None
        return SimpleNamespace(
            saved_job_id=saved_job_id,
            title="Platform Engineer",
            company="Example",
            location="Remote",
            status="saved",
            tags=["platform"],
            notes=None,
            raw_jd_text="Build Kubernetes platforms.",
            latest_analysis=None,
            archived_at=None,
        )


def _match(**metadata) -> KnowledgeMatch:
    return KnowledgeMatch(
        chunk_id="chunk-1",
        score=0.92,
        text="[资源] 用户收藏职位\n[职位] Platform Engineer\n[公司] Example\nKubernetes",
        metadata=metadata,
    )


def test_personal_knowledge_query_uses_authenticated_scope_and_returns_citation() -> None:
    service = _KnowledgeService([
        _match(
            resource_type="saved_job",
            resource_id="job-1",
            owner_user_id="user-1",
            visibility="private",
            resource_version=2,
            document_id="document-1",
        )
    ])

    outcome = search_personal_knowledge(
        "哪些岗位需要 Kubernetes？",
        user_id="user-1",
        allowed_sources=["saved_jobs"],
        service=service,
        sync_repository=_StatusRepository(),  # type: ignore[arg-type]
        profile_repository=_ProfileRepository(),  # type: ignore[arg-type]
        job_repository=_JobRepository(),  # type: ignore[arg-type]
    )

    assert service.calls == [{
        "query": "哪些岗位需要 Kubernetes？",
        "user_id": "user-1",
        "resource_types": ("saved_job",),
        "top_k": 6,
        "include_public": False,
    }]
    assert outcome.warnings == []
    assert outcome.sources == ["saved_jobs"]
    assert outcome.evidence[0].citation.citation_id == "saved_job:job-1"
    assert outcome.evidence[0].citation.label == "Platform Engineer · Example"
    assert outcome.evidence[0].content["retrieval_source"] == "modular_rag_mcp"
    assert outcome.evidence[0].content["current_resource"]["jd_excerpt"] == (
        "Build Kubernetes platforms."
    )
    assert set(outcome.timings_ms) == {
        "query_expansion",
        "mcp_query",
        "hydrate_and_validate",
        "total",
    }
    assert all(value >= 0 for value in outcome.timings_ms.values())


def test_personal_knowledge_adds_bounded_bilingual_search_aliases() -> None:
    service = _KnowledgeService([])

    search_personal_knowledge(
        "哪个职位需要生理信号机器学习经验？",
        user_id="user-1",
        allowed_sources=["saved_jobs"],
        service=service,
        sync_repository=_StatusRepository(),  # type: ignore[arg-type]
        profile_repository=_ProfileRepository(),  # type: ignore[arg-type]
        job_repository=_JobRepository(),  # type: ignore[arg-type]
    )

    assert service.calls[0]["query"] == (
        "哪个职位需要生理信号机器学习经验？\n"
        "Search aliases: physiological signal; machine learning"
    )


def test_personal_knowledge_rejects_foreign_and_stale_results() -> None:
    service = _KnowledgeService([
        _match(
            resource_type="saved_job",
            resource_id="job-foreign",
            owner_user_id="other-user",
            visibility="private",
            resource_version=2,
            document_id="document-1",
        ),
        _match(
            resource_type="saved_job",
            resource_id="job-stale",
            owner_user_id="user-1",
            visibility="private",
            resource_version=1,
            document_id="document-1",
        ),
    ])

    outcome = search_personal_knowledge(
        "saved jobs",
        user_id="user-1",
        allowed_sources=["saved_jobs"],
        service=service,
        sync_repository=_StatusRepository(ready=False),  # type: ignore[arg-type]
        profile_repository=_ProfileRepository(),  # type: ignore[arg-type]
        job_repository=_JobRepository(),  # type: ignore[arg-type]
    )

    assert outcome.evidence == []
    assert "personal_knowledge_result_rejected:scope" in outcome.warnings
    assert "personal_knowledge_result_rejected:stale" in outcome.warnings
    assert "personal_knowledge_no_usable_matches" in outcome.warnings


def test_personal_knowledge_rejects_deleted_current_business_resource() -> None:
    service = _KnowledgeService([
        _match(
            resource_type="saved_job",
            resource_id="job-deleted",
            owner_user_id="user-1",
            visibility="private",
            resource_version=2,
            document_id="document-1",
        )
    ])

    outcome = search_personal_knowledge(
        "Kubernetes",
        user_id="user-1",
        allowed_sources=["saved_jobs"],
        service=service,
        sync_repository=_StatusRepository(),  # type: ignore[arg-type]
        profile_repository=_ProfileRepository(),  # type: ignore[arg-type]
        job_repository=_JobRepository(available=False),  # type: ignore[arg-type]
    )

    assert outcome.evidence == []
    assert "personal_knowledge_result_rejected:stale" in outcome.warnings
