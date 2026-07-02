# Deleted Files - 2026-06-25 Cleanup

Cleanup date: 2026-06-25  
Branch: `codex/v4-curated-job-crawler-provider`

This cleanup removed old source files and tests that were no longer part of the
current v4 product path. The goal was to reduce stale code before the next Job
Search iteration, while keeping enough notes to make rollback or later recovery
easy.

## Deletion Rule Used

Files were deleted only when all of these were true:

- no current `/api/v1` route, application usecase, repository, frontend API, or
  provider imports the file;
- the file was covered only by a direct old unit test, not by the live product
  flow;
- the current replacement path is already present elsewhere in the repository.

Generated files such as `__pycache__`, `.pytest_cache`, `web/dist`, and
experiment output reports were not cleaned in this pass.

## Deleted Files

| Deleted file | Type | Why it was removed | Current replacement / current path | Restore note |
| --- | --- | --- | --- | --- |
| `app/services/search_query_service.py` | old service | Early helper that generated hardcoded role/location queries directly from raw resume text. It was not used by Search Preview or Job Search. | `app/services/job_search_planner.py`, `app/services/job_search_intent.py`, and provider-specific preview/search mapping in `app/application/job_search_usecases.py`. | Restore only if a dedicated query helper is needed again; prefer rebuilding it around `ConfirmedProfile` and `JobSearchIntent`, not raw resume text. |
| `tests/test_search_query_service.py` | old test | Tested only the removed `search_query_service.py` behavior, including fixed software-role query rules. | Current query behavior is covered by `tests/test_job_search_planner.py`, `tests/test_job_search_intent.py`, `tests/test_job_search_api.py`, and `tests/test_frontend_search_preview_flow.py`. | Restore with the service only; otherwise it protects an obsolete path. |
| `app/services/confirmed_profile_storage_service.py` | old service | Wrote to the old `confirmed_profile_records` table using older `ResumeProfile` confirmation schemas. Current v4 confirmation uses repository/usecase storage. | `app/repositories/confirmed_profile_repository.py`, `app/application/confirmed_profile_usecases.py`, and `profile_draft_service.confirm_profile_draft`. | If old record exports are needed, recover this file and reconnect it deliberately as a legacy adapter. |
| `tests/test_confirmed_profile_storage_service.py` | old test | Tested only the removed old storage service and its old table path. | Current confirmed profile behavior is covered by `tests/test_confirmed_profile_api.py`, `tests/test_profile_draft_api.py`, `tests/test_profile_draft_service.py`, and repository-oriented tests. | Restore only if the old `confirmed_profile_records` path is intentionally revived. |
| `app/services/jd_url_service.py` | old utility | Standalone JD URL import helper was not referenced by current API routes or the Job Search provider pipeline. Current live search gets JD text through provider candidates and provider-specific detail strategies. | `app/services/job_search_providers/*`, especially provider `RawJobCandidate.raw_description`; JD analysis still runs through `app/agents/jd_analysis_agent.py`. | Restore if a user-facing "import JD from URL" feature is added as a separate product surface. |
| `tests/test_jd_url_service.py` | old test | Tested only the removed standalone JD URL import helper. | Provider/detail crawling tests now live in `tests/test_cuhksz_career_provider.py`, `tests/test_serper_web_provider.py`, `tests/test_linkedin_discovery_provider.py`, and `tests/test_remoteok_provider.py`. | Restore with a revived JD URL import feature. |

## Not Deleted In This Pass

These related files were intentionally kept:

- `app/storage/database.py`: still contains old tables, but DB cleanup is a
  migration-sensitive task and should be done separately.
- Old confirmed-profile schema classes in `app/schemas/confirmed_profile.py`:
  `profile_review_quality_evaluation.py` still references
  `ConfirmedProfileCreateRequest`.
- `app/services/search_ready_profile_builder.py`: still used by
  `app/services/profile_draft_service.py`.
- `app/services/mock_pipeline.py`: despite the name, current resume/JD agents
  still import deterministic helpers from it.
- `app/services/resume_profile_enrichment_service.py` and
  `app/prompts/profile_enrichment/`: still useful as evaluation/support context
  until resume extraction strategy is fully settled.

## Verification

Run after this cleanup:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m compileall app experiments
cd web
npm run build
```
