from __future__ import annotations

from app.repositories.job_search_repository import JobSearchRepository
from app.schemas.job_search import JobSearchTraceStep

TRACE_STEP_NAMES = [
    "Search planning",
    "Provider search",
    "Candidate filtering",
    "JD analysis",
    "Profile matching",
    "Result assembly",
]

PLANNING_GUARDRAILS = [
    "Only derive job search intent from the confirmed profile.",
    "Do not invent missing work history, domain experience, or credentials.",
]
FILTER_GUARDRAILS = [
    "Only rank candidates returned by the search provider.",
    "Do not create or merge candidates.",
]
ASSEMBLY_GUARDRAILS = [
    "Only return jobs backed by provider results and source metadata.",
    "Do not invent source URLs or provider names.",
]


def _create_initial_trace_steps(
    run_id: str,
    repository: JobSearchRepository,
) -> list[JobSearchTraceStep]:
    return [
        repository.create_trace_step(
            job_search_run_id=run_id,
            step_index=index + 1,
            name=name,
            status="pending",
            mode="deterministic",
            summary="Queued.",
        )
        for index, name in enumerate(TRACE_STEP_NAMES)
    ]


def _ensure_trace_steps(run_id: str, repository: JobSearchRepository) -> list[JobSearchTraceStep]:
    steps = repository.list_trace_steps(run_id)
    if steps:
        return steps
    return _create_initial_trace_steps(run_id, repository)


def _find_running_or_pending_step(steps: list[JobSearchTraceStep]) -> JobSearchTraceStep | None:
    for status in ("running", "pending"):
        for step in steps:
            if step.status == status:
                return step
    return None
