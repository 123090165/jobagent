# Cleanup Audit

Audit date: 2026-06-18.

Scope: non-destructive cleanup audit for separating the current v4 product line
from older tracker, Streamlit, workflow, provider, and demo artifacts. No tracked
source files or folders were deleted in this pass.

## Current mainline architecture

The current intended product line is:

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

The current v4 runtime shape is:

- FastAPI backend in `app/`.
- Resource/application flow under `app/api/v1`, `app/application`,
  `app/repositories`, `app/schemas`, `app/services`, and `app/storage`.
- Vue frontend in `web/`.
- Tests in `tests/`.
- Current v4 docs, especially `docs/V4_PRODUCT_REFACTOR_PLAN.md`,
  `docs/V4_STATE_MACHINE.md`, `docs/V4_ERROR_CONTRACT.md`,
  `docs/V4_FRONTEND_ROUTE_GUARDS.md`, `docs/API_CONTRACT_V1.md`, and
  `docs/SEARCH_PROVIDER.md`.

Important safety note: `app/main.py` still includes several unversioned legacy
routers. Anything reachable from those routers is still live FastAPI surface and
is not a delete candidate until the API surface is intentionally retired.

## Keep

| Path | Classification | Notes |
| --- | --- | --- |
| `app/` | keep | Backend runtime. Contains both v4 core and legacy subareas listed below. |
| `app/api/v1/` | keep | Current v4 resource API. |
| `app/application/` | keep | Current v4 usecase layer. |
| `app/repositories/` | keep | Current persistence repositories. |
| `app/schemas/` | keep | Shared API/domain contracts; contains both v4 and legacy schemas. |
| `app/services/` | keep | Runtime services; contains both v4 services and legacy provider/workflow support. |
| `app/storage/` | keep | SQLite connection/repository helpers. |
| `app/main.py` | keep | FastAPI app assembly. Also documents which legacy routers are still live. |
| `web/` | keep | Current Vue frontend. |
| `tests/` | keep | Regression coverage, including coverage for legacy surfaces that are still live. |
| `.github/` | keep | CI workflow. |
| `requirements.txt` | keep | Runtime/test dependency manifest. Some dependencies are legacy candidates but not safe to remove yet. |
| `.env.example` | keep | Safe tracked environment example. |
| `data/jd_examples/`, `data/samples/` | keep | Tracked sample inputs. |
| `docs/V4_*.md`, `docs/API_CONTRACT_V1.md` | keep | Current v4 planning and API contract docs. |
| `docs/SEARCH_PROVIDER.md` | keep | Still relevant, but should eventually distinguish old `/search/jobs` from v4 job-search-run providers more clearly. |

Top-level areas that are not delete candidates but need review:

| Path | Classification | Notes |
| --- | --- | --- |
| `.ai/` | needs_review | Development prompts/skills. Not runtime, but may be useful project metadata. |
| `docs/` | needs_review | Mixed current docs, old workflow docs, and generated demo outputs. |
| `scripts/` | needs_review | Mostly demos/evaluations; several are imported by tests. |
| `job_agent_prepare.md` | deleted | Historical preparation/planning document deleted in the follow-up repository-size cleanup. |
| `data/*.sqlite3` | delete_candidate | Ignored local SQLite outputs, not tracked. Preserve manually if needed before local cleanup. |
| `.venv/`, `.pytest_cache/`, `__pycache__/`, `web/dist/`, `web/node_modules/` | delete_candidate | Ignored generated/local environment artifacts. Do not commit. |

## Archive candidates

These are candidates for a later archive phase, not delete candidates in this
pass.

| Path | Classification | Reason |
| --- | --- | --- |
| `frontend/` | archive_candidate | Legacy Streamlit demo/admin panel. `web/` is the current frontend. `frontend/profile_review_state.py` is still imported by `app/services/profile_review_quality_evaluation.py`, so extract shared helpers before archiving. |
| `app/workflows/` | archive_candidate | Legacy analysis workflow and LangGraph prototype. Still imported by `/analyze/full`, `application_service`, `batch_brief_service`, `mock_pipeline`, scripts, and tests. |
| `app/api/routes_analyze.py` | archive_candidate | Legacy full-analysis endpoint; still included by `app/main.py`. |
| `app/api/routes_applications.py` | archive_candidate | Old application tracker API; still included by `app/main.py`. |
| `app/api/routes_records.py` | archive_candidate | Old records/report storage API; still included by `app/main.py`. |
| `app/api/routes_job_import_candidates.py` | archive_candidate | Old candidate import API; still included by `app/main.py`. |
| `app/services/application_service.py` | archive_candidate | Old application tracker service; imported by legacy router and tests. |
| `app/services/job_import_candidate_service.py` | archive_candidate | Old candidate import flow; imported by legacy router, scripts, and tests. |
| `app/schemas/application.py` | archive_candidate | Old tracker schema; still imported by legacy services/routes and `app/schemas/api.py`. |
| `app/schemas/job_import_candidate.py` | archive_candidate | Old job import schema; still imported by legacy service, scripts, and tests. |
| `app/services/search_providers/` | archive_candidate | Older provider layer for `/search/jobs` with `mock`, `local_db`, and `gemini_cli`. Still imported by `app/services/job_search_service.py`. |
| `app/services/live_job/` | archive_candidate | Older `cuhksz_live` provider implementation; still imported by `job_search_service` and tests. |
| `app/services/public_job_storage_service.py` | archive_candidate | Supports old local DB/live provider path; still imported by provider code, scripts, and tests. |
| `app/agents/match_agent.py`, `app/agents/report_agent.py`, `app/agents/resume_optimize_agent.py` | archive_candidate | Primarily used by old workflow and tests. |
| `app/agents/missing_info_agent.py`, `app/agents/project_challenge_agent.py` | archive_candidate | Primarily used by old workflow and tests. |
| `scripts/demo_*.py`, `scripts/run_*_evaluation.py`, `scripts/run_*_experiments.py` | archive_candidate | Demo/evaluation utilities. Several are still test-covered, so archive only with test updates. |
| `docs/demo_outputs/` | deleted | Generated evaluation/demo outputs deleted in the follow-up repository-size cleanup. |
| `docs/demo_runs/` | deleted | Historical demo run snapshot deleted in the follow-up repository-size cleanup. |

## Delete candidates

No tracked source or documentation file is safe to delete in this first pass.

Safe local/ignored delete candidates after preserving anything manually needed:

- `.pytest_cache/`
- `__pycache__/` folders
- `.streamlit-out.log`
- `.streamlit-err.log`
- `web/dist/`
- `demo_runs/`
- `data/*.sqlite3`
- `data/*.sqlite3-*`
- `app/services/job_search_providers/adapters/__pycache__/`

`web/node_modules/` and `.venv/` are generated local dependency folders, but
they are also useful for local checks. They should remain ignored, not tracked.

## Outdated docs

Current docs:

- `docs/V4_PRODUCT_REFACTOR_PLAN.md`
- `docs/V4_ARCHITECTURE_PLAN.md`
- `docs/V4_STATE_MACHINE.md`
- `docs/V4_ERROR_CONTRACT.md`
- `docs/V4_FRONTEND_ROUTE_GUARDS.md`
- `docs/API_CONTRACT_V1.md`
- `docs/SEARCH_PROVIDER.md`
- `docs/CONFIRMED_PROFILE_PERSISTENCE.md`
- `docs/PROFILE_DRAFT_EDITING_UI.md`
- `docs/PROFILE_FLOW_DECOUPLING.md`
- `docs/SEARCH_READY_PROFILE_LAYER.md`

Outdated or legacy-positioned docs:

- `README.md`: still presents the old `Job Source -> SearchResultItem ->
  JobImportCandidate -> ApplicationRecord -> Application Deep Analysis ->
  Evidence-based Final Report` loop as core, recommends Streamlit demo usage,
  and names `local_db`, `gemini_cli`, and `cuhksz_live` as primary providers.
- `docs/APPLICATION_TRACKER.md`
- `docs/JOB_IMPORT_CANDIDATE.md`
- `docs/WORKFLOW_ARCHITECTURE.md`
- `docs/WORKFLOW_QUALITY_SMOKE_TEST.md`
- `docs/WORKFLOW_TRACE_PERSISTENCE.md`
- `docs/LANGGRAPH_MIGRATION_PREP.md`
- `docs/LANGGRAPH_WORKFLOW_PROTOTYPE.md`
- `docs/DEMO_GUIDE.md`
- `docs/DEMO_SCRIPT.md`
- `docs/DEMO_GEMINI_SEARCH_FLOW.md`
- `docs/REAL_GEMINI_JD_EXPERIMENTS.md`
- `docs/REAL_LOCAL_JOB_BRIEF_DEMO.md`
- `docs/OLLAMA_LLM_WORKFLOW_EVALUATION.md`
- `docs/STREAMLIT_APP.md`

Docs that need review because they may mix old and current concepts:

- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_OVERVIEW.md`
- `docs/DATA_SCHEMA.md`
- `docs/STORAGE.md`
- `docs/AGENTS.md`
- `docs/AGENT_BOUNDARIES.md`
- `docs/AGENT_TRACE.md`
- `docs/LIVE_JOB_PROVIDER.md`
- `docs/PUBLIC_JOB_SOURCE_PROVIDER.md`
- `docs/LLM_INTEGRATION.md`
- `docs/LLM_PROMPT_AND_QUALITY_CONTROL.md`

Deleted historical artifacts:

- `docs/demo_outputs/**`
- `docs/demo_runs/**`
- `job_agent_prepare.md`

## Possibly unused dependencies

| Dependency | Classification | Findings |
| --- | --- | --- |
| `streamlit` | legacy_candidate | Imported by `frontend/profile_review_flow.py` and `frontend/streamlit_app.py`. Not part of the Vue/FastAPI v4 mainline, but needed while keeping the Streamlit demo. |
| `langgraph` | legacy_candidate | Imported by `app/workflows/langgraph_job_analysis_workflow.py`. Still exposed through `/analyze/full` via `use_langgraph_workflow` and covered by tests. Do not remove before retiring that route/flag/tests. |
| `requests` | legacy_candidate | Imported by `app/services/live_job/fetcher.py`, which supports the older `cuhksz_live` provider path. Not used by the newer `app/services/job_search_providers/cuhksz_career_provider.py`, which uses `urllib`. |
| `beautifulsoup4` | required_now | Imported as `bs4` by both `app/services/job_search_providers/cuhksz_career_provider.py` and `app/services/live_job/parsers/cuhksz.py`. Required for current CUHKSZ parsing. |
| `httpx` | test_only | No direct project import found. FastAPI/Starlette `TestClient` depends on it for tests, so keep while tests use `TestClient`. |
| `python-multipart` | required_now | No direct import expected. Required by FastAPI for `UploadFile = File(...)` endpoints, including `app/api/v1/profile_sessions.py` and `app/api/routes_resume.py`. |

## Import dependency findings

Import checks were run against tracked Python files using AST import analysis
and text search for runtime dependency names.

- `app/main.py` still imports and includes legacy routers:
  `routes_analyze`, `routes_applications`, `routes_job_import_candidates`,
  `routes_records`, `routes_search`, `routes_reports`, and others. Their
  backing modules are not safe to delete.
- `app/workflows/job_analysis_workflow.py` is imported by
  `app/api/routes_analyze.py`, `app/services/application_service.py`,
  `app/services/batch_brief_service.py`, `app/services/mock_pipeline.py`,
  `app/workflows/langgraph_job_analysis_workflow.py`, tests, and scripts.
- `app/workflows/langgraph_job_analysis_workflow.py` is imported by
  `app/api/routes_analyze.py` and tests.
- `app/workflows/graph_spec.py` is imported by `app/workflows/__init__.py` and
  `tests/test_graph_spec.py`; it is a `test_only_legacy_candidate` once package
  export compatibility is handled.
- `app/services/application_service.py` is imported by
  `app/api/routes_applications.py` and tests.
- `app/services/job_import_candidate_service.py` is imported by
  `app/api/routes_job_import_candidates.py`, `scripts/demo_job_import_candidate.py`,
  and tests.
- `app/services/search_providers/gemini_cli_provider.py` and
  `app/services/search_providers/local_public_job_provider.py` are imported by
  `app/services/search_providers/__init__.py`; that package is imported by
  `app/services/job_search_service.py`.
- `app/services/live_job/provider.py` is imported by
  `app/services/job_search_service.py` and tests.
- `app/services/public_job_storage_service.py` is imported by
  `app/services/live_job/provider.py`,
  `app/services/search_providers/local_public_job_provider.py`, scripts, and
  tests.
- `frontend/profile_review_flow.py` is Streamlit-facing and imported by tests;
  from the FastAPI/Vue mainline perspective it is a `test_only_legacy_candidate`.
- `frontend/profile_review_state.py` is not safe to archive by itself because
  `app/services/profile_review_quality_evaluation.py` imports helper functions
  from it.
- `app/agents/jd_analysis_agent.py` should be kept: it is used by the v4 job
  search usecase and older routes/workflows.
- `app/agents/resume_parse_agent.py` should be kept while current resume parsing
  routes/services use it.
- `app/agents/match_agent.py`, `report_agent.py`, `resume_optimize_agent.py`,
  `missing_info_agent.py`, and `project_challenge_agent.py` are legacy workflow
  archive candidates, not delete candidates.

## Recommended cleanup phases

1. Documentation alignment: update README and docs index so v4 ProfileSession
   flow is clearly primary and old tracker/demo docs are labeled legacy.
2. API surface inventory: decide which unversioned FastAPI routes remain
   supported, which become legacy-only, and which can be retired after tests are
   moved or deleted.
3. Streamlit extraction: move shared helpers out of `frontend/profile_review_state.py`
   into an `app/` module, then archive `frontend/` as a demo/admin surface.
4. Provider consolidation: choose between the newer
   `app/services/job_search_providers/` path and older
   `app/services/search_providers/` plus `app/services/live_job/` path. Remove
   `local_db`, `gemini_cli`, `cuhksz_live`, and `requests` only after API and
   test coverage are intentionally retired or migrated.
5. Workflow cleanup: retire or archive `/analyze/full`, `app/workflows/`, and
   LangGraph-specific code if the v4 product no longer uses application deep
   analysis as a first-class flow.
6. Agent/report cleanup: after workflow retirement, reclassify old match,
   report, resume optimization, missing-info, and project-challenge agents for
   archive or removal.
7. Generated artifact cleanup: `docs/demo_outputs/`, `docs/demo_runs/`, and
   `job_agent_prepare.md` were removed after confirming they were not part of
   current runtime or tests.
8. Dependency cleanup: remove dependencies only after import checks and full
   backend/frontend checks pass in the same cleanup branch.

## Files changed in this cleanup

- Added `docs/CLEANUP_AUDIT.md`.
- Added a short README note pointing to this audit.

No files were deleted or moved.
