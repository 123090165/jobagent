"""用固定语料离线评估个人 RAG 的召回与排序质量，并输出 JSON 报告。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.config.env_loader import load_local_env
from app.repositories.resume_profile_repository import ResumeProfileRepository
from app.repositories.rag_sync_repository import rag_sync_repository
from app.repositories.saved_job_repository import SavedJobRepository
from app.repositories.user_repository import UserRepository
from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJobCreateRequest
from app.services.chat_personal_knowledge import search_personal_knowledge
from app.services.mcp.modular_rag import resolve_modular_rag_service
from app.services.rag_management import resolve_rag_management_client
from app.services.rag_sync_worker import RAGSyncWorker
from app.storage.database import get_connection, init_database
from experiments.rag_quality.evaluator import (
    evaluate_rankings,
    lexical_rankings,
    load_corpus,
    write_report,
)
from experiments.rag_quality.schemas import RAGFixtureDocument, RAGQualityCorpus


DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "rag_quality"
    / "fixtures"
    / "career_private_v1.json"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the repeatable private-career RAG relevance fixture."
    )
    parser.add_argument("--mode", choices=("lexical", "live"), default="lexical")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-hit-rate", type=float, default=1.0)
    parser.add_argument("--min-mrr", type=float, default=0.75)
    args = parser.parse_args(argv)
    if not 0 <= args.min_hit_rate <= 1:
        parser.error("--min-hit-rate must be between 0 and 1")
    if not 0 <= args.min_mrr <= 1:
        parser.error("--min-mrr must be between 0 and 1")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    load_local_env()
    args = parse_args(argv)
    corpus = load_corpus(args.fixture)
    if args.mode == "lexical":
        report = evaluate_rankings(
            corpus,
            rankings=lexical_rankings(corpus),
            mode="lexical",
        )
    else:
        report = _run_live(corpus)
    print(report.model_dump_json(indent=2))
    if args.output:
        write_report(report, args.output)
    failed = (
        report.forbidden_hit_count > 0
        or report.hit_rate < args.min_hit_rate
        or report.mean_reciprocal_rank < args.min_mrr
    )
    return 1 if failed else 0


def _run_live(corpus: RAGQualityCorpus):
    management_client = resolve_rag_management_client()
    rag_service = resolve_modular_rag_service()
    if management_client is None or rag_service is None:
        raise RuntimeError(
            "live mode requires RAG management and MCP URLs plus the shared service token"
        )

    with tempfile.TemporaryDirectory(
        prefix="jobagent-rag-eval-",
        ignore_cleanup_errors=True,
    ) as temp_dir:
        with _temporary_environment(
            JOBAGENT_DB_PATH=str(Path(temp_dir) / "jobagent.sqlite3"),
            JOBAGENT_RAG_SYNC_ENABLED="true",
        ):
            users = UserRepository()
            primary = users.create(
                username=f"rag-eval-primary-{uuid4()}",
                password_hash="evaluation-only",
                password_salt="evaluation-only",
                password_algorithm="evaluation-only",
            )
            other = users.create(
                username=f"rag-eval-other-{uuid4()}",
                password_hash="evaluation-only",
                password_salt="evaluation-only",
                password_algorithm="evaluation-only",
            )
            jobs = SavedJobRepository()
            profiles = ResumeProfileRepository()
            worker = RAGSyncWorker(
                management_client,
                profile_repository=profiles,
                job_repository=jobs,
            )
            document_ids: dict[str, str] = {}
            created: list[tuple[str, str, str]] = []
            rankings: dict[str, list[str]] = {}
            latencies: dict[str, float] = {}
            try:
                for document in corpus.documents:
                    owner_id = (
                        primary.user_id
                        if document.owner == "primary"
                        else other.user_id
                    )
                    resource_id = _create_document(
                        document,
                        user_id=owner_id,
                        jobs=jobs,
                        profiles=profiles,
                    )
                    document_ids[document.document_key] = resource_id
                    created.append((document.resource_type, owner_id, resource_id))

                indexed = asyncio.run(worker.run_once(limit=100))
                if indexed.failed or indexed.completed != len(created):
                    raise RuntimeError(
                        "fixture indexing failed "
                        f"(completed={indexed.completed}, failed={indexed.failed})"
                    )
                reverse_ids = {
                    resource_id: document_key
                    for document_key, resource_id in document_ids.items()
                }
                for case in corpus.cases:
                    started = perf_counter()
                    result = search_personal_knowledge(
                        case.query,
                        user_id=primary.user_id,
                        allowed_sources=[
                            "profile"
                            if resource_type == "resume_profile"
                            else "saved_jobs"
                            for resource_type in case.resource_types
                        ],
                        top_k=case.top_k,
                        service=rag_service,
                    )
                    latencies[case.case_id] = (perf_counter() - started) * 1_000
                    rankings[case.case_id] = [
                        reverse_ids[resource_id]
                        for evidence in result.evidence
                        if (resource_id := evidence.citation.resource_id) in reverse_ids
                    ]
            finally:
                for resource_type, owner_id, resource_id in created:
                    if resource_type == "saved_job":
                        jobs.archive(user_id=owner_id, saved_job_id=resource_id)
                    else:
                        profiles.archive(
                            user_id=owner_id,
                            resume_profile_id=resource_id,
                        )
                if created:
                    deleted = asyncio.run(worker.run_once(limit=100))
                    if deleted.failed or deleted.completed != len(created):
                        raise RuntimeError(
                            "fixture cleanup failed "
                            f"(completed={deleted.completed}, failed={deleted.failed})"
                        )
            return evaluate_rankings(
                corpus,
                rankings=rankings,
                mode="live",
                latencies_ms=latencies,
            )


def _create_document(
    document: RAGFixtureDocument,
    *,
    user_id: str,
    jobs: SavedJobRepository,
    profiles: ResumeProfileRepository,
) -> str:
    if document.resource_type == "saved_job":
        job = jobs.save(
            user_id=user_id,
            payload=SavedJobCreateRequest.model_validate(document.payload),
        )
        return job.saved_job_id
    profile = _create_fixture_profile(document, user_id=user_id)
    return profile.resume_profile_id


def _create_fixture_profile(
    document: RAGFixtureDocument,
    *,
    user_id: str,
) -> ResumeProfile:
    now = datetime.now(timezone.utc)
    payload = document.payload
    target_roles = _strings(payload.get("target_roles"))
    profile = ResumeProfile(
        resume_profile_id=str(uuid4()),
        user_id=user_id,
        name=str(payload.get("name") or (target_roles[0] if target_roles else "Profile")),
        summary=str(payload.get("summary", "")),
        target_roles=target_roles,
        target_directions=_strings(payload.get("target_directions")),
        core_skills=_strings(payload.get("core_skills")),
        supporting_skills=_strings(payload.get("supporting_skills")),
        search_keywords=_strings(payload.get("search_keywords")),
        preferred_locations=_strings(payload.get("preferred_locations")),
        work_arrangements=_strings(payload.get("work_arrangements")),
        strengths=_strings(payload.get("strengths")),
        risks=_strings(payload.get("risks")),
        profile=dict(payload),
        is_default=True,
        created_at=now,
        updated_at=now,
    )
    with get_connection() as connection:
        init_database(connection)
        connection.execute(
            """
            INSERT INTO resume_profiles (
                resume_profile_id, user_id, source_session_id,
                source_confirmed_profile_id, name, summary,
                target_roles_json, target_directions_json, core_skills_json,
                supporting_skills_json, search_keywords_json,
                preferred_locations_json, work_arrangements_json,
                strengths_json, risks_json, profile_json, raw_resume_text,
                is_default, archived_at, created_at, updated_at
            ) VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, NULL, ?, ?)
            """,
            (
                profile.resume_profile_id,
                user_id,
                profile.name,
                profile.summary,
                json.dumps(profile.target_roles),
                json.dumps(profile.target_directions),
                json.dumps(profile.core_skills),
                json.dumps(profile.supporting_skills),
                json.dumps(profile.search_keywords),
                json.dumps(profile.preferred_locations),
                json.dumps(profile.work_arrangements),
                json.dumps(profile.strengths),
                json.dumps(profile.risks),
                json.dumps(profile.profile),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        rag_sync_repository.enqueue(
            connection=connection,
            user_id=user_id,
            resource_type="resume_profile",
            resource_id=profile.resume_profile_id,
            operation="upsert",
        )
        connection.commit()
    return profile


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


@contextmanager
def _temporary_environment(**values: str):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
