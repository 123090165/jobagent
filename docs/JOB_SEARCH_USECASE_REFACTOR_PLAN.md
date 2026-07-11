# Job Search Use Case Refactor Plan

## Purpose

Refactor app/application/job_search_usecases.py into focused modules without
changing product behavior. This is a behavior-preserving structural change, not
a search-quality redesign and not an agent-framework migration.

The document is intentionally detailed so a smaller coding model can execute
one phase at a time. A stronger model or human should review each phase before
the next one starts.

## Current Problem

job_search_usecases.py is about 1,945 lines and currently owns:

- API-facing use cases and authorization;
- run creation and lifecycle;
- search preview construction;
- analysis/model configuration;
- browser-helper and current-page adapters;
- provider execution and recall diagnostics;
- concurrent JD analysis;
- candidate matching and result assembly;
- trace creation and failure handling;
- local mock result construction;
- general formatting helpers.

These responsibilities change for different reasons. Continuing to add features
to this file increases merge conflicts, makes isolated tests harder, and raises
the risk that a provider or scoring change affects run lifecycle behavior.

## Scope

This refactor may:

- move functions and small data classes into focused modules;
- rename private functions inside their new modules;
- add typed internal result structures when they replace loose dictionaries
  without changing serialized output;
- update imports and focused tests;
- leave temporary compatibility imports in job_search_usecases.py.

This refactor must not:

- add OpenAI Agents SDK, LangGraph, LangChain, or another orchestrator;
- change API routes, Pydantic response shapes, or error codes;
- change database tables, migration behavior, repository SQL, or ownership;
- change prompts, scoring formulas, query budgets, provider selection, or
  candidate limits;
- change fallback rules, warning text, trace names, trace order, or detail keys;
- change concurrency defaults, maximums, ordering, or exception behavior;
- change deterministic result IDs;
- convert the execution model to asyncio, a queue, or a worker;
- remove Ollama/mock/provider abstractions;
- perform unrelated large-file cleanup.

## Preconditions

1. Review git status.
2. Preserve all existing user changes.
3. Commit or otherwise establish a known baseline for the current timing and
   documentation work before starting the refactor.
4. Run the baseline tests listed below and record the result.
5. Do not use reset, checkout, or broad formatting to obtain a clean tree.

If baseline tests fail, stop and distinguish existing failures from refactor
failures before moving code.

## Required Stable Behavior

The following are compatibility contracts even when they are not public APIs:

- public functions remain importable from
  app.application.job_search_usecases;
- create_job_search_run returns before or after execution exactly as it does
  today for BackgroundTasks and direct-test execution;
- browser-helper candidates preserve their source metadata and warnings;
- ThreadPoolExecutor.map preserves selected-candidate order;
- one JD failure falls back for that candidate instead of failing the run;
- run failure marks the active trace step and run as failed;
- TRACE_STEP_NAMES remains in the current six-step order;
- timing values may vary, but timing key names and measured boundaries remain;
- local mock mode does not require a network connection or an LLM;
- deterministic result IDs continue to use the current UUID5 inputs;
- result deduplication continues to use candidate_recall_key;
- repository ownership checks continue to receive the same user_id.

## Target Structure

Create a small package:

~~~text
app/services/job_search_execution/
  __init__.py
  browser_capture.py
  candidate_analysis.py
  preview.py
  provider_search.py
  result_builder.py
  trace.py
~~~

Keep this file:

~~~text
app/application/job_search_usecases.py
~~~

Its final responsibility is:

- authorize and load owning resources;
- create and retrieve JobSearchRun resources;
- schedule or execute a run;
- coordinate the six stages;
- persist lifecycle and trace transitions;
- translate stage results into repository writes;
- expose the existing public use-case functions.

Do not introduce a generic framework base class. Plain functions and focused
data classes are sufficient.

## Function Ownership Map

### job_search_usecases.py

Keep:

- create_job_search_run
- create_browser_helper_job_search_run
- analyze_browser_job_capture
- execute_job_search_run
- get_job_search_run
- list_job_search_trace_steps
- list_job_search_runs
- preview_job_search_run

The application module may also retain the small analysis configuration
resolution functions until preview extraction is complete.

Keep _compose_browser_helper_provider here during this refactor. It composes
the injected browser payload provider with selected backend providers for the
application use case; moving it is optional only if provider_search.py can own
it without importing application state.

### browser_capture.py

Move:

- browser_job_capture_to_candidate
- _browser_helper_candidate_to_raw
- _capture_summary
- _browser_capture_report
- _browser_capture_warnings
- _trace_quality_warnings if it remains capture-only

Keep analyze_browser_job_capture in the application module because it loads
owned workflow resources and creates a persisted run.

### candidate_analysis.py

Move:

- _analyze_candidates
- _analyze_candidate_for_job_search
- _jd_analysis_concurrency
- _summarize_candidate_timings
- _truncate_detail_text
- _summarize_analysis_mode

Keep the current ThreadPoolExecutor behavior and per-candidate fallback.

### provider_search.py

Move:

- ProviderQueryStat
- ProviderRecallResult
- _run_provider_search
- _provider_source_attempts
- _provider_source_count
- _effective_provider_locations
- _provider_source_kind
- _elapsed_ms, or replace it with an equivalent private helper in this module

ProviderRecallResult.details() must return the same keys and value shapes.

### result_builder.py

Move:

- _build_local_mock_results
- _match_candidates
- _assemble_results
- _metadata_risks
- _is_boilerplate_browser_helper_warning
- _confidence_label_for_score
- _recommended_action
- _source_provider_counts

Do not change score calculations, sorting, risk text, action text, or UUID5
construction.

### preview.py

Move:

- _resolve_search_inputs
- _resolve_selected_sources
- _build_provider_preview_searches
- _search_source_notes
- _estimate_query_budget
- _augment_search_plan
- _augment_search_plan_from_inputs
- _recall_queries_from_plan
- _ranking_signals_from_plan
- _provider_name_from_selected_sources

Move analysis configuration helpers only if doing so does not introduce a
dependency from services back into application:

- _uses_job_search_analysis
- JobSearchAnalysisConfig
- _resolve_job_search_analysis_config
- _resolve_browser_helper_analysis_config
- _resolve_requested_llm_provider
- _resolve_execution_analysis_enabled
- _resolve_execution_llm_provider

It is acceptable to keep this configuration group in job_search_usecases.py
during the first refactor.

### trace.py

Move:

- TRACE_STEP_NAMES
- PLANNING_GUARDRAILS
- FILTER_GUARDRAILS
- ASSEMBLY_GUARDRAILS
- _create_initial_trace_steps
- _ensure_trace_steps
- _find_running_or_pending_step

This module may call JobSearchRepository methods, but it must not own run
authorization or the full run lifecycle.

### Shared Helpers

_clean_list is used across several groups. Do not create a broad utils.py only
for this function. Choose one of these:

1. keep a small private copy in modules where behavior is trivial; or
2. move the existing behavior to an already appropriate normalization service.

Do not create a dependency cycle just to centralize one helper.

## Dependency Direction

Allowed:

~~~text
app/api/v1
-> app/application/job_search_usecases
-> app/services/job_search_execution
-> existing services, agents, schemas, and provider interfaces

app/application/job_search_usecases
-> repositories
~~~

Disallowed:

~~~text
job_search_execution
-> app.application.job_search_usecases

provider adapters
-> application use cases

schemas
-> services or repositories
~~~

FastAPI BackgroundTasks remains in the application module. New execution
service modules must not depend on FastAPI.

## Migration Strategy

Perform one phase at a time. After each phase, run focused tests and review the
diff. Do not combine all moves into one patch.

### Phase 0: Baseline

- Record current function inventory.
- Run baseline tests.
- Confirm no existing imports rely on private functions except known tests.
- Add characterization tests only where a move would otherwise be unsafe.
- Make no production behavior changes.

Exit criteria:

- baseline tests pass;
- current work is committed or clearly separated;
- no undocumented behavior decision is required.

### Phase 1: Result Builder

Reason: matching and assembly are leaf behavior with little lifecycle coupling.

Steps:

1. Add result_builder.py.
2. Move local mock construction, matching, assembly, risk, score-label, action,
   source-count, and result-ID helpers without rewriting them.
3. Import them into job_search_usecases.py using the existing private names
   where practical.
4. Keep test_job_search_result_assembly.py passing.
5. Add focused tests only for behavior currently uncovered and at risk.

Exit criteria:

- result objects and ordering are unchanged;
- deterministic IDs are unchanged;
- job_search_usecases.py no longer contains matching/assembly implementation.

### Phase 2: Candidate Analysis

Steps:

1. Add candidate_analysis.py.
2. Move bounded parallel JD analysis and its diagnostics as one unit.
3. Inject JSONChatLLM exactly as today.
4. Preserve executor.map ordering and exception fallback.
5. Keep environment-variable parsing unchanged.

Exit criteria:

- concurrency tests pass;
- fallback counts, mode summaries, warnings, and timing keys are unchanged;
- no new global executor or semaphore is introduced.

### Phase 3: Provider Search

Steps:

1. Add provider_search.py.
2. Move ProviderQueryStat and ProviderRecallResult before moving execution.
3. Move provider-loop, deduplication, caps, source attempts, and timing together.
4. Preserve provider.search_jobs call order and break conditions.
5. Preserve details() output exactly.

Exit criteria:

- live API and recall metric tests pass;
- fake providers receive the same queries, locations, and limits;
- duplicate and truncation counts are unchanged.

### Phase 4: Browser Capture

Steps:

1. Add browser_capture.py.
2. Move deterministic payload conversion and report/warning construction.
3. Keep application orchestration and persistence in
   analyze_browser_job_capture.
4. Preserve extractor metadata and warning text.

Exit criteria:

- browser capture API and extension source tests pass;
- no cookies, authentication data, or new page data enter backend payloads.

### Phase 5: Preview And Configuration

Steps:

1. Add preview.py.
2. Move preview-only plan augmentation, source descriptions, URLs, and budget
   calculations.
3. Move analysis configuration only if dependency direction remains clean.
4. Keep preview_job_search_run as the authorized application entry point.

Exit criteria:

- preview response fields and source ordering are unchanged;
- preview does not create a run;
- provider and LLM selection remain independent.

### Phase 6: Trace Helpers And Orchestrator Cleanup

Steps:

1. Add trace.py.
2. Move trace constants and lifecycle helper functions.
3. Remove temporary compatibility imports that have no remaining callers.
4. Organize execute_job_search_run as a readable six-stage coordinator.
5. Do not replace the coordinator with a generic pipeline engine.

Exit criteria:

- trace order, statuses, summaries, detail keys, and failure behavior match the
  baseline;
- public application use-case signatures remain unchanged;
- job_search_usecases.py contains orchestration rather than stage internals;
- no circular imports exist.

## Compatibility Import Policy

Existing tests import _assemble_results from job_search_usecases.py. During
Phases 1-5, preserve this with an import alias:

~~~python
from app.services.job_search_execution.result_builder import (
    assemble_results as _assemble_results,
)
~~~

Use the same approach only for known callers. At Phase 6, either:

- update tests to import the owning service; or
- retain a documented compatibility alias if another runtime caller exists.

Do not maintain aliases for every old private helper indefinitely.

## Testing Plan

### Baseline And Final Backend Checks

~~~powershell
.venv\Scripts\python.exe -m compileall app
.venv\Scripts\python.exe -m pytest
~~~

### Phase 1

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_job_search_result_assembly.py tests/test_job_search_api.py -q
~~~

### Phase 2

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_job_search_analysis_concurrency.py tests/test_jd_analysis_agent.py tests/test_job_search_live_api.py -q
~~~

### Phase 3

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_job_search_live_api.py tests/test_job_search_recall_metrics.py tests/test_job_search_provider_status_api.py -q
~~~

### Phase 4

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_browser_job_capture_api.py tests/test_browser_job_capture_extension.py tests/test_job_search_api.py -q
~~~

### Phase 5

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_job_search_planner.py tests/test_job_search_intent.py tests/test_job_search_api.py tests/test_frontend_search_preview_flow.py -q
~~~

### Phase 6

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_job_search_trace_repository.py tests/test_job_search_api.py tests/test_job_search_live_api.py -q
cd web
npm run build
~~~

After every phase:

~~~powershell
git diff --check
git status --short
~~~

The frontend build is required at the end even if Vue source is unchanged,
because search response types and trace details are consumed by the frontend.

## Review Checklist For Each Phase

- Is the diff mainly movement plus import changes?
- Did any string, score, limit, query order, dictionary key, or warning change?
- Did a service begin importing an application module?
- Did dependency injection become global state?
- Did a repository call move into provider, scoring, or prompt code?
- Are exceptions still caught at the same boundary?
- Are partial results and fallback behavior unchanged?
- Are sensitive payloads still excluded from traces and logs?
- Do focused tests and diff checks pass?

If a phase requires a product decision, stop. Record the decision separately
instead of silently combining it with structural movement.

## Completion Criteria

The refactor is complete when:

- all current public use-case functions remain available;
- all backend tests pass;
- the Vue production build passes;
- job_search_usecases.py is primarily an application facade and coordinator;
- stage implementations can be tested without run lifecycle setup;
- no new framework or production dependency was added;
- API, database, provider behavior, scoring, trace shape, and fallback behavior
  are unchanged;
- canonical architecture and development docs match the final module layout.

## Suggested Model Assignment

A smaller coding model may execute one phase at a time if given:

- this document;
- the current repository;
- permission to stop on failed tests;
- an explicit instruction not to continue into the next phase.

Use a stronger reasoning model or human review for:

- Phase 0 boundary confirmation;
- any circular-dependency resolution;
- changes to loose dictionary contracts;
- Phase 6 orchestrator review;
- any proposed deviation from the prohibited-change list.

Do not ask one smaller model to execute all phases in one uninterrupted task.
