# Cleanup Audit

Audit date: 2026-06-19.

This audit now records the completed destructive cleanup pass that followed the
earlier non-destructive inventory.

## Current mainline architecture

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

Runtime shape:

- FastAPI v4 API under `app/api/v1/`.
- Usecase layer under `app/application/`.
- Persistence repositories under `app/repositories/`.
- Current schemas and services under `app/schemas/` and `app/services/`.
- SQLite connection helpers under `app/storage/`.
- Vue frontend under `web/`.
- Current regression tests under `tests/`.

## Keep

- `app/api/v1/`
- `app/application/`
- `app/repositories/`
- `app/schemas/`
- `app/services/`
- `app/storage/`
- `app/main.py`
- `web/`
- `tests/`
- `README.md`
- Current docs including `docs/V4_PRODUCT_REFACTOR_PLAN.md`,
  `docs/SEARCH_PROVIDER.md`, and this cleanup documentation.

## Archive candidates

No `_archive/` folder is used. The obvious obsolete artifacts were deleted
instead of moved.

## Delete candidates

Handled in this cleanup:

- Streamlit `frontend/`.
- Old unversioned API routes.
- Old full-analysis/LangGraph workflow and workflow-only agents.
- Old tracker/import services and schemas.
- Old `/search/jobs` provider stack and old provider tests.
- Old demo/evaluation scripts.
- Docs that only described removed legacy flows.

Remaining possible delete candidates require a doc-by-doc review:

- Mixed-era docs such as `docs/API.md`, `docs/ARCHITECTURE.md`,
  `docs/ARCHITECTURE_OVERVIEW.md`, `docs/DATA_SCHEMA.md`, and `docs/STORAGE.md`.

## Outdated docs

Deleted during this cleanup:

- Application tracker and job import docs.
- Streamlit docs.
- LangGraph/workflow docs.
- Batch brief/rerank docs.
- Old live/local/Gemini provider docs.
- Old demo and evaluation docs.

Needs review rather than automatic deletion:

- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_OVERVIEW.md`
- `docs/DATA_SCHEMA.md`
- `docs/STORAGE.md`
- `docs/AGENTS.md`
- `docs/AGENT_BOUNDARIES.md`
- `docs/AGENT_TRACE.md`

## Possibly unused dependencies

Removed after import checks and passing tests:

- `streamlit`
- `langgraph`
- `requests`

Kept:

- `beautifulsoup4`: current CUHKSZ provider uses `bs4`.
- `httpx`: test client dependency.
- `python-multipart`: FastAPI upload endpoint dependency.

## Import dependency findings

- `app/main.py` now includes only health plus `/api/v1` routers.
- `frontend/` has no remaining backend importers; helper code moved to
  `app/services/profile_review_state_helpers.py`.
- `app/workflows/` and workflow-only agents had no current v4 callers after old
  routes/tests were retired.
- Old provider paths had no v4 callers after the current CUHKSZ parser helpers
  were moved into `app/services/job_search_providers/cuhksz_career_provider.py`.
- No `streamlit`, `langgraph`, or `requests` imports remain.

## Recommended cleanup phases

Completed in this pass:

1. Remove Streamlit frontend.
2. Retire old unversioned routers.
3. Remove workflow/tracker/import code.
4. Consolidate providers around `mock` and `cuhksz_career`.
5. Remove legacy-only dependencies and docs.

Recommended next phase:

1. Review mixed-era docs and align or delete them.
2. Run a schema/storage review for old SQLite tables that may remain in local
   developer databases.
3. Keep v4 API and frontend tests as the safety rail for future cleanup.

## Files changed in this cleanup

See the commit diff for the full staged deletion list. The main additions were:

- `app/services/profile_review_state_helpers.py`
- Updated `README.md`
- Updated `docs/CLEANUP_AUDIT.md`
- Updated `docs/LEGACY_MAP.md`
