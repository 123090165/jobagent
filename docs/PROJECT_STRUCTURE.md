# JobAgent Project Structure

Last reviewed: 2026-07-02
Branch reviewed: `codex/v4-curated-job-crawler-provider`

This document is a working map of the current repository before starting the
next Job Search iteration. It focuses on what each area is for, whether it is
part of the live product path, and where documentation or code may have drifted.

## Current Product Flow

```text
Vue frontend
-> /api/v1 FastAPI routes
-> application usecases
-> services / agents / providers
-> repositories
-> SQLite data/jobagent.sqlite3
```

User-facing flow:

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Search Preview
-> Job Search Run
-> Job Brief later
```

`Job Brief` is still planned, not active. Current work should keep focusing on
resume truthfulness, search recall, candidate preservation, and ranking quality.

## Top-Level Layout

| Path | Status | Purpose |
| --- | --- | --- |
| `app/` | live runtime | FastAPI backend, usecases, schemas, repositories, services, providers, prompts. |
| `web/` | live runtime | Vue 3 + Pinia + Naive UI frontend. |
| `tests/` | active | Backend, service, API, parser, provider, and frontend-helper regression tests. |
| `docs/` | active but partly drifted | Product, API, architecture, cleanup, and planning docs. |
| `experiments/` | experiment-only | Local DeepSeek resume extraction comparison, multidomain flow checks, and provider recall calibration; not production runtime. |
| `browser-helper/` | browser extension | Chrome/Edge helper for user-triggered current-page job capture. |
| `data/` | local runtime data | SQLite database and local generated state. Should not be treated as source. |
| `.ai/` | local/supporting | Local assistant or project-support metadata. Not part of the app runtime. |
| `.github/` | repo support | GitHub configuration if present. |
| `.venv/`, `.pytest_cache/`, `web/node_modules/`, `web/dist/`, `__pycache__/` | generated/ignored | Development artifacts, not source architecture. |

## Backend Runtime Map

### `app/main.py`

Live entry point. Creates the FastAPI app, loads local env files, registers
`/health`, installs the `JobAgentError` JSON handler, and includes all current
`/api/v1` routers.

Registered routers:

- `profile_sessions`
- `profile_drafts`
- `confirmed_profiles`
- `job_search_runs`
- `job_search_providers`
- `llm`

### `app/api/v1/`

Live public API surface used by the Vue frontend.

| File | Status | Purpose |
| --- | --- | --- |
| `profile_sessions.py` | live | Create/load sessions, submit resume text/file, get resume, parse resume, create draft, list job-search runs. |
| `profile_drafts.py` | live | Get/update profile drafts and confirm a draft. |
| `confirmed_profiles.py` | live | Load a persisted confirmed profile. |
| `job_search_runs.py` | live | Preview search, create a run, fetch run status, fetch trace steps. |
| `job_search_providers.py` | live | Provider status endpoint for mock, native job-board/API, search-engine, and multi-source providers. |
| `llm.py` | live | LLM status endpoint for explicit providers such as DeepSeek, Ollama, and mock. |

### `app/application/`

Live usecase layer. This is where API routes are translated into product
operations and persistence changes.

| File | Status | Purpose |
| --- | --- | --- |
| `profile_session_usecases.py` | live | Session create/load helpers. |
| `resume_intake_usecases.py` | live | Resume text/file intake and downstream invalidation. |
| `resume_review_usecases.py` | live | Parsed resume review creation, cache/regenerate behavior, deterministic/LLM-guided review. |
| `profile_draft_usecases.py` | live | Draft generation and update from parsed review. |
| `confirmed_profile_usecases.py` | live | Confirm a draft into a search-ready confirmed profile. |
| `job_search_usecases.py` | live and central | Search preview, run creation, trace execution, provider calls, filtering, JD analysis, matching, result assembly. |

`job_search_usecases.py` is the main file to understand before v4.7. It owns the
current traced pipeline:

```text
Search planning
-> Provider search
-> Candidate filtering
-> JD analysis
-> Profile matching
-> Result assembly
```

### `app/repositories/`

Live SQLite-backed persistence layer. Repositories serialize Pydantic models into
JSON columns and update `ProfileSession.current_step`.

| File | Status | Purpose |
| --- | --- | --- |
| `profile_session_repository.py` | live | `ProfileSession` persistence and step transitions. |
| `resume_document_repository.py` | live | Uploaded/pasted resume storage. |
| `parsed_resume_review_repository.py` | live | Parsed review persistence with analysis mode/provider/warnings. |
| `profile_draft_repository.py` | live | Editable draft persistence. |
| `confirmed_profile_repository.py` | live | Current confirmed profile persistence. |
| `job_search_repository.py` | live | Job search runs, results JSON, and trace steps. |

### `app/storage/database.py`

Live database initializer, but it still contains old tables from pre-v4 flows:
`resume_records`, `job_postings`, `match_reports`, `project_challenges`,
`analysis_records`, `resume_versions`, `workflow_step_traces`, and
`application_records`.

The current v4 tables are:

- `profile_sessions`
- `resume_documents`
- `parsed_resume_reviews`
- `profile_drafts`
- `confirmed_profiles`
- `job_search_runs`
- `job_search_trace_steps`

The old tables appear to be compatibility residue. They are not central to the
current Vue `/api/v1` flow and should be treated carefully before deletion.

## Backend Services And Agents

### Resume/Profile Services

| File | Status | Purpose |
| --- | --- | --- |
| `resume_section_parser.py` | live | Deterministic section-based resume parser. Must not invent projects or work experience. |
| `resume_skill_lexicon.py` | live support | Skill vocabulary used by parser/profile logic. |
| `resume_profile_review_service.py` | live | Builds profile review result from deterministic parser. |
| `resume_llm_review_service.py` | live | Guided LLM resume review with deterministic fallback and sanitized warnings. |
| `profile_draft_service.py` | live | Builds and confirms editable profile drafts. |
| `search_ready_profile_builder.py` | live | Deterministic conversion from parsed review to search-ready profile signals. |
| `search_signal_normalizer.py` | live | Normalizes role/skill/search signals. |
| `profile_enrichment_quality.py` | active support/tests | Quality utilities for enrichment suggestions. |
| `resume_profile_enrichment_service.py` | support/older enrichment path | Used by quality evaluation/tests; not the main current Resume Review path. |
| `profile_review_quality_evaluation.py` | evaluation support | Offline quality evaluation helper; not request-time runtime. |
| `resume_profile_evaluation.py` | support | Evaluation helper around profile review output. |
| `profile_review_state_helpers.py` | active support/tests | Shared helper logic retained from frontend review behavior. |

### LLM And Prompt Services

| File/Path | Status | Purpose |
| --- | --- | --- |
| `llm_provider.py` | live | Resolves provider-agnostic LLM services; DeepSeek is the current default while Ollama remains selectable. |
| `llm_service.py` | live | OpenAI-compatible JSON chat completion service. |
| `config/env_loader.py` | live | Loads local env files, including the DeepSeek local env workflow. |
| `prompts/loader.py` | live | Safe UTF-8 prompt loading from `app/prompts`. |
| `prompts/jd_analysis/` | live | JD analysis prompt. |
| `prompts/shared/` | live | JSON/evidence/anti-hallucination policies for prompts. |
| `prompts/profile_enrichment/` | support | Used by enrichment service/tests, not the main v4.6.1 review path. |
| `prompts/project_challenge/` | currently dormant | Prompt assets for a later project challenge feature. |

### Job Search Services

| File | Status | Purpose |
| --- | --- | --- |
| `job_search_planner.py` | live and central | Builds search plan and focused provider queries from confirmed profile plus user inputs. |
| `job_candidate_filter.py` | live | Ranks provider-returned candidates before analysis. Should not invent candidates. |
| `job_search_recall_metrics.py` | live support/experiment support | Shared source-level recall metrics for runtime trace details and provider calibration reports. |
| `job_search_providers/base.py` | live | Shared provider interface and `RawJobCandidate`. |
| `job_search_providers/mock_provider.py` | live/test/demo | Deterministic provider for tests and local fallback. |
| `job_search_providers/cuhksz_career_provider.py` | live | Public CUHKSZ search/list/detail parser. Current main live provider. |
| `job_search_providers/linkedin_discovery_provider.py` | live | Serper-backed public LinkedIn job-link discovery; does not scrape LinkedIn detail pages. |
| `job_search_providers/remoteok_provider.py` | live | RemoteOK public JSON API provider. |
| `job_search_providers/serper_web_provider.py` | optional live | Serper Google Search API provider for public job-link discovery. |
| `job_search_providers/multi_source_provider.py` | live | Aggregates selected source providers into one candidate pool. |
| `job_search_providers/browser_helper_provider.py` | browser-assisted payload path | Consumes candidates returned by the JobAgent Browser Helper extension. |
| `jd_analysis_quality.py` | live | Quality gate for LLM JD extraction. |
| `jd_quality_service.py` | live/tested | JD quality scoring helpers. |
| `mock_pipeline.py` | live support | Deterministic legacy-style parser/profile support still used indirectly by profile review paths. |

### Agents

| File | Status | Purpose |
| --- | --- | --- |
| `agents/resume_parse_agent.py` | live via review/experiment | Thin wrapper around deterministic resume parsing. |
| `agents/jd_analysis_agent.py` | live | JD analysis with deterministic baseline, LLM proposal, quality gate, fallback. |
| `agents/schemas.py` | live | Agent output schemas. |
| `agents/types.py` | live support | Shared agent typing. |

## Schemas

`app/schemas/` contains Pydantic contracts for API, persistence snapshots, and
service outputs.

Most active schema groups:

- `profile_session.py`
- `resume_document.py`
- `parsed_resume_review.py`
- `profile_draft.py`
- `confirmed_profile.py`
- `job_search.py`
- `job_search_provider.py`
- `llm.py`
- `resume.py`
- `profile_review.py`
- `search_ready_profile.py`
- `job.py`
- `jd_quality.py`

`resume_intake.py`, `profile_enrichment.py`, and related older profile-review
schemas remain useful for current tests/supporting services, even where not all
fields are directly surfaced in the main frontend.

## Frontend Runtime Map

### `web/src/router/index.ts`

Live Vue route table.

Current routes:

- `/`
- `/profile/:sessionId/review`
- `/profile/:sessionId/draft`
- `/profile/:sessionId/confirmed`
- `/profile/:sessionId/search-preview`
- `/jobs/:runId`

Route guards exist for draft, confirmed profile, and search preview, but the
review and job-search pages are less strictly guarded.

### `web/src/api/`

| File | Status | Purpose |
| --- | --- | --- |
| `client.ts` | live | Axios client configuration. |
| `profileSessions.ts` | live | Typed API wrapper for all current `/api/v1` frontend calls. |

### `web/src/stores/profileSession.ts`

Live Pinia store and the main frontend state coordinator. It owns:

- session lifecycle
- resume submission
- resume review loading/regeneration
- LLM status
- draft editing/confirmation
- search preview
- search run creation/loading/polling
- provider status

### `web/src/services/`

| File | Status | Purpose |
| --- | --- | --- |
| `browserHelper.ts` | live | Frontend bridge to the Chrome/Edge Browser Helper extension. |
| `bossSearchPlanning.ts` | live | BOSS query localization and empty-result diagnostic message formatting. |
| `jobSearchSources.ts` | live | Shared source labels, provider-key parsing, and source-selection normalization. |

### `web/src/pages/`

| File | Status | Purpose |
| --- | --- | --- |
| `HomePage.vue` | live | Resume intake. |
| `ProfileReviewPage.vue` | live | Resume analysis visibility, LLM switch/status, parsed review. |
| `ProfileDraftPage.vue` | live | Editable search-ready profile draft. |
| `ProfileConfirmedPage.vue` | live | Confirmed profile display and transition to search preview. |
| `SearchPreviewPage.vue` | live and recent | Shows planned search intent/provider queries before starting search. |
| `JobSearchPage.vue` | live | Search run status, trace timeline, and results. |

### `web/src/types/profileSession.ts`

Live TypeScript contracts matching backend response shapes. This file must stay
aligned with `app/schemas/*`.

## Experiments

Experiment scripts are not production runtime.

`experiments/resume_extraction_compare.py` compares DeepSeek extraction modes:

- `direct_one_shot`
- `direct_fieldwise`
- `guided_reconciliation`

It imports app/test fixtures and calls DeepSeek only when explicitly run with an
env file. Outputs go under `experiments/output/`, which should not be committed.

`experiments/README.md` is current for this experiment.

`experiments/multidomain_flow_check.py` runs synthetic resumes through resume
review, profile draft, confirmed profile, and search preview without live LLMs
or live providers.

`experiments/provider_recall_calibration.py` runs live provider recall checks
for `multi_source`, individual sources, or `serper_web`; setup uses
deterministic search intent and does not call DeepSeek.

`experiments/provider_live_smoke.py` runs one provider query through the shared
`JobSearchProvider` interface and reports whether live public candidates, source
URLs, and optional detail text are available.

## Tests

The test suite is active and broad. Important clusters:

- API flow: `test_profile_session_api.py`, `test_resume_intake_api.py`,
  `test_resume_review_api.py`, `test_profile_draft_api.py`,
  `test_confirmed_profile_api.py`, `test_job_search_api.py`,
  `test_job_search_live_api.py`
- Resume/parser: `test_resume_section_parser.py`,
  `test_resume_parser_regression_corpus.py`,
  `test_resume_profile_review_service.py`, `test_resume_review_usecases.py`
- LLM/provider: `test_llm_provider.py`, `test_llm_status_api.py`,
  `test_resume_profile_enrichment_service.py`
- Job search: `test_job_search_planner.py`,
  `test_job_candidate_filter.py`, `test_cuhksz_career_provider.py`,
  `test_linkedin_discovery_provider.py`, `test_remoteok_provider.py`,
  `test_serper_web_provider.py`, `test_job_search_recall_metrics.py`,
  `test_job_search_provider_status_api.py`, `test_job_search_trace_repository.py`
- Frontend helper/flow coverage: `test_frontend_profile_review_helpers.py`,
  `test_frontend_search_preview_flow.py`
- Experiment: `test_resume_extraction_compare_experiment.py`,
  `test_provider_recall_calibration_experiment.py`,
  `test_provider_live_smoke_experiment.py`

The latest local focused provider check before this document was:

```text
.venv\Scripts\python.exe -m pytest tests\test_cuhksz_career_provider.py
12 passed
```

## Docs Inventory

| Doc | Current usefulness | Notes |
| --- | --- | --- |
| `README.md` | current entry point | Good quick-start and high-level directory summary. Mentions Job Brief as future. |
| `docs/INDEX.md` | current | Points to v4.7 Job Search Reliability and current cleanup records. |
| `docs/API_CONTRACT_V1.md` | partially current | Useful route contract, but missing `/api/v1/job-search-runs/preview` and still frames Job Brief as planned v4.6. |
| `docs/V4_PRODUCT_REFACTOR_PLAN.md` | partially outdated | Good architecture history, but current next step no longer directly Job Brief. |
| `docs/NEXT_DEV_PLAN.md` | current | Tracks v4.7 search reliability stages and postpones Job Brief until search/ranking are reliable. |
| `docs/SEARCH_PROVIDER.md` | current | Provider boundary, multi-source path, source-level recall stats, and calibration experiment. |
| `docs/SEARCH_READY_PROFILE_LAYER.md` | mostly current, version wording old | Describes profile layer well, but refers to v3.9a/v3.9b naming. |
| `docs/V4_STATE_MACHINE.md` | mostly current | Useful state and invalidation rules. May need Search Preview mention. |
| `docs/V4_ERROR_CONTRACT.md` | current | Error shape and codes still relevant. |
| `docs/V4_FRONTEND_ROUTE_GUARDS.md` | partially aspirational | Good guard rules, but router implementation is lighter than the doc recommends. |
| `docs/PROFILE_FLOW_DECOUPLING.md` | historical/current context | Useful explanation of decoupling and provider switch, but versioned as v3.9c. |
| `docs/CONFIRMED_PROFILE_PERSISTENCE.md` | partially outdated | Describes an older `/profile/confirmed` API; current v4 path uses `/api/v1/profile-drafts/{id}/confirm` and `/api/v1/confirmed-profiles/{id}`. |
| `docs/LLM_ASSISTED_PROFILE_ENRICHMENT.md` | support/older path | Describes enrichment route that is not the current primary v4 resume review route. |
| `docs/LLM_PROMPT_AND_QUALITY_CONTROL.md` | current for JD analysis | Useful for JD agent quality gate and LLM fallback policy. |
| `docs/PROFILE_REVIEW_QUALITY_EVALUATION.md` | partially outdated | Still references old `scripts/run_profile_review_quality_evaluation.py`; current experiment lives under `experiments/`. |
| `docs/SECTION_BASED_RESUME_PARSER.md` | current concept, minor encoding issue | Useful parser design and guardrails; one example line has mojibake. |
| `docs/CLEANUP_AUDIT.md` | historical audit | Valuable cleanup record from 2026-06-19. |
| `docs/LEGACY_MAP.md` | historical guardrail | Useful to prevent restoring deleted legacy runtime. |
| `docs/GIT_WORKFLOW.md` | current | Still matches current branch/commit/check workflow. |
| `docs/PROJECT_STRUCTURE.md` | current map | This file. |

## Current Drift / Cleanup Notes

These are not immediate blockers, but they matter before larger v4.7 work:

1. `docs/API_CONTRACT_V1.md` and `docs/V4_PRODUCT_REFACTOR_PLAN.md` still need
   a later refresh to reflect the Search Preview and multi-source provider path.
2. `docs/API_CONTRACT_V1.md` should include Search Preview:
   `POST /api/v1/job-search-runs/preview`.
3. Older historical docs may still mention v4.6 Job Brief as the immediate next
   step. The canonical current plan is `docs/NEXT_DEV_PLAN.md`.
4. `app/storage/database.py` contains older pre-v4 tables. They are probably
   harmless, but the live v4 table set should be made explicit before any DB
   cleanup.
5. `confirmed_profile_storage_service.py`, `jd_url_service.py`, and
   `search_query_service.py` were removed in the 2026-06-25 cleanup. See
   `docs/DELETED_FILES_2026_06_25.md`.
6. `experiments/web_search_recall_check.py` was removed in the 2026-07-02
   provider recall cleanup. See `docs/DELETED_FILES_2026_07_02.md`.
7. Some enrichment/project-challenge prompt paths are tested or preserved, but
   not central to the current runtime flow.
8. Frontend route guards are implemented but simpler than the recommended doc.
   This is acceptable for now, but should be revisited when search/brief routes
   become more complex.

## Cleanup Candidate Markers

These files or schema areas are not marked for deletion yet. They are marked so
future cleanup can be discussed and tested deliberately.

| Area | Marker | Current evidence | Recommended action |
| --- | --- | --- | --- |
| `app/storage/database.py` old tables: `resume_records`, `job_postings`, `match_reports`, `project_challenges`, `analysis_records`, `resume_versions`, `workflow_step_traces`, `application_records` | legacy compatibility residue | Current v4 runtime repositories primarily use `profile_sessions`, `resume_documents`, `parsed_resume_reviews`, `profile_drafts`, `confirmed_profiles`, `job_search_runs`, and `job_search_trace_steps`. | Do not delete in v4.7. First confirm no active repository/test/data migration still depends on these tables. |
| `app/services/confirmed_profile_storage_service.py` | deleted 2026-06-25 | Current v4 confirmed profile runtime uses `confirmed_profile_repository.py` plus `confirmed_profile_usecases.py`. | See `docs/DELETED_FILES_2026_06_25.md` for restore notes. |
| `app/services/jd_url_service.py` | deleted 2026-06-25 | Current Job Search enters through providers and `RawJobCandidate`, not user-submitted JD URLs. | See `docs/DELETED_FILES_2026_06_25.md` for restore notes. |
| `app/services/resume_profile_enrichment_service.py` | older enrichment path | Used by quality/evaluation tests and older docs. Main Resume Review now uses deterministic review plus `resume_llm_review_service.py` guided review/fallback. | Keep as reference/evaluation support. Consider merging or deleting only after resume extraction strategy is settled. |
| `app/prompts/profile_enrichment/` | older enrichment prompts | Supports the older enrichment service rather than the current guided review path. | Keep with the service for now; do not expand unless the older enrichment path is revived. |
| `app/prompts/project_challenge/` | dormant future feature | No current product route for project challenge questions. | Keep as dormant prompt assets. Reassess when implementing interview/job brief follow-up features. |
| `app/services/search_query_service.py` | deleted 2026-06-25 | Current Search Preview and provider query logic lives in `job_search_planner.py`, `job_search_intent.py`, and provider-specific mapping. | See `docs/DELETED_FILES_2026_06_25.md` for restore notes. |
| `experiments/web_search_recall_check.py` | deleted 2026-07-02 | Serper-only recall experiment was superseded by generic provider recall calibration. | See `docs/DELETED_FILES_2026_07_02.md` for restore notes. |
| `app/services/mock_pipeline.py` | suspicious name, still useful | Despite the name, current resume/profile review paths may still depend on deterministic parsing helpers. | Do not remove without import-level and behavior-level tests. Rename later only if it remains part of the live deterministic parser path. |

Cleanup rule for these markers:

```text
mark -> confirm references -> run tests -> remove only if runtime and tests agree
```

## v4.7 Orientation

Before starting v4.7, the files most likely to matter are:

- `app/application/job_search_usecases.py`
- `app/services/job_search_planner.py`
- `app/services/job_search_recall_metrics.py`
- `app/services/job_candidate_filter.py`
- `app/services/job_search_providers/base.py`
- `app/services/job_search_providers/cuhksz_career_provider.py`
- `app/services/job_search_providers/linkedin_discovery_provider.py`
- `app/services/job_search_providers/remoteok_provider.py`
- `app/services/job_search_providers/serper_web_provider.py`
- `app/services/job_search_providers/multi_source_provider.py`
- `app/services/job_search_providers/browser_helper_provider.py`
- `app/repositories/job_search_repository.py`
- `app/schemas/job_search.py`
- `browser-helper/background.js`
- `web/src/pages/SearchPreviewPage.vue`
- `web/src/pages/JobSearchPage.vue`
- `web/src/services/browserHelper.ts`
- `web/src/services/bossSearchPlanning.ts`
- `web/src/services/jobSearchSources.ts`
- `web/src/stores/profileSession.ts`
- `web/src/types/profileSession.ts`
- `tests/test_job_search_planner.py`
- `tests/test_job_candidate_filter.py`
- `tests/test_cuhksz_career_provider.py`
- `tests/test_job_search_api.py`
- `tests/test_job_search_live_api.py`

The most valuable next architectural move is not a large refactor. It is to
make the existing job search chain more observable:

```text
search plan
-> provider queries
-> candidate pool
-> source stats
-> quality flags
-> ranking bands
-> final displayed results
```

That keeps the current v4 flow intact while giving future multi-platform search
and evidence-based scoring a clean place to attach.
