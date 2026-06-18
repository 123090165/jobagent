# Legacy Map

This map records legacy areas that remain in the repository after the Phase 2
cleanup. These areas are not part of the current v4 mainline, but they are still
reachable by imports, routes, tests, scripts, or local demo workflows. They
should not be deleted until their callers are intentionally removed or migrated.

## Current v4 mainline

The current product flow is:

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

Primary mainline areas:

- `app/api/v1/`
- `app/application/`
- `app/repositories/`
- `app/schemas/`
- `app/services/`
- `app/storage/`
- `app/main.py`
- `web/`
- `tests/`

Current user-facing frontend:

- `web/` is the Vue frontend.
- `frontend/` is not the main user frontend.

Current v4 job-search providers:

- `mock`
- `cuhksz_career`

## Legacy areas still reachable

`frontend/` is the old Streamlit demo/admin surface. It is not the mainline
frontend, but it cannot be archived wholesale yet because
`app/services/profile_review_quality_evaluation.py` imports helpers from
`frontend/profile_review_state.py`. Some tests also import Streamlit-facing
helper code.

`app/workflows/` contains the old full analysis and LangGraph workflow path. It
is still imported by the old `/analyze/full` route, tests, and scripts. It also
feeds older analysis/report behavior used outside the v4 ProfileSession path.

Old unversioned API routes are still included by `app/main.py` or remain part of
the tested API surface:

- `app/api/routes_analyze.py`
- `app/api/routes_applications.py`
- `app/api/routes_records.py`
- `app/api/routes_job_import_candidates.py`
- `app/api/routes_search.py`
- `app/api/routes_reports.py`

Old provider paths remain reachable:

- `app/services/search_providers/`
- `app/services/live_job/`
- `app/services/public_job_storage_service.py`

These support older provider names and flows such as `local_db`, `gemini_cli`,
and `cuhksz_live`. They are not the current v4 provider set, but they are still
imported by legacy services, tests, and scripts.

The old tracker/import flow remains reachable through application tracker and
job import candidate modules:

- `app/api/routes_applications.py`
- `app/api/routes_job_import_candidates.py`
- `app/services/application_service.py`
- `app/services/job_import_candidate_service.py`
- `app/schemas/application.py`
- `app/schemas/job_import_candidate.py`

Old agents primarily used by the legacy workflow remain in place:

- `app/agents/match_agent.py`
- `app/agents/report_agent.py`
- `app/agents/resume_optimize_agent.py`
- `app/agents/project_challenge_agent.py`
- `app/agents/missing_info_agent.py`

These should be treated as legacy workflow dependencies unless a current v4
caller is identified during a future import audit.

## Archive candidates not moved yet

The following are archive candidates, but were intentionally not moved in Phase
2 because they are still imported, routed, or covered by tests:

- `frontend/`
- `app/workflows/`
- old unversioned API routes
- old tracker/import services and schemas
- `app/services/search_providers/`
- `app/services/live_job/`
- `app/services/public_job_storage_service.py`
- old workflow-centered agents
- demo/evaluation scripts under `scripts/`
- legacy docs that describe ApplicationRecord, JobImportCandidate, LangGraph,
  Streamlit, or old demo workflows

Historical generated outputs and notes removed during cleanup:

- `docs/demo_outputs/` was deleted after being identified as generated
  evaluation/demo output.
- `docs/demo_runs/` was deleted after being identified as a historical demo run
  snapshot.
- `job_agent_prepare.md` was deleted after being identified as a historical
  preparation note.

These files were not part of the current v4 mainline and were not required by
tests or runtime. Deleting them reduced repository file count and size.

## Dependencies blocked by legacy areas

Do not remove these dependencies yet:

- `streamlit`: still used by `frontend/`.
- `langgraph`: still used by `app/workflows/langgraph_job_analysis_workflow.py`
  and tests around the old workflow path.
- `requests`: still used by `app/services/live_job/fetcher.py`.
- `beautifulsoup4`: required by current `cuhksz_career` parsing and old live-job
  parsing.
- `httpx`: used indirectly by FastAPI/Starlette `TestClient` in tests.
- `python-multipart`: required by FastAPI `UploadFile = File(...)` endpoints.

Dependency removal should happen only after the owning legacy route/module is
retired and the full backend and frontend checks pass.

## Future deletion plan

1. Extract shared helpers from `frontend/profile_review_state.py` into an `app/`
   module, update imports, then archive or remove the Streamlit surface.
2. Decide whether `/analyze/full` and the old full-analysis workflow remain
   supported. If not, remove the route, update tests, and archive
   `app/workflows/`.
3. Retire or version the old tracker/import endpoints before removing
   ApplicationRecord and JobImportCandidate services and schemas.
4. Consolidate provider code around the v4 `mock` and `cuhksz_career` provider
   path, then remove old `local_db`, `gemini_cli`, and `cuhksz_live` code.
5. Reclassify old workflow agents after workflow retirement; delete only agents
   with no v4 importers and no retained tests.
6. Delete or rewrite legacy docs once README and doc links no longer depend on
   them as current product documentation.
7. Remove blocked dependencies one at a time, with import checks and full test
   runs after each dependency change.
