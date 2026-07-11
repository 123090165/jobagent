# Architecture

## Runtime Shape

~~~text
Vue web application
  -> /api/v1
FastAPI routes
  -> application use cases
  -> domain services and provider adapters
  -> repositories
  -> SQLite in local development

Chrome/Edge browser helper
  -> Vue bridge for BOSS search
  -> FastAPI for current-page analysis
~~~

Current boundaries:

- app/api/v1: HTTP transport and dependencies;
- app/application: use-case orchestration and ownership checks;
- app/services: parsing, quality rules, LLM interface, and providers;
- app/repositories: persistence queries and model reconstruction;
- app/schemas: Pydantic contracts;
- app/storage: database initialization and compatibility helpers;
- web/src/api: typed HTTP clients;
- web/src/stores: user and workflow state;
- web/src/pages: product views;
- browser-helper: local browser-assisted provider and capture extension.

The Vue application uses HTTP contracts and never imports backend code. Provider
and LLM credentials remain server-side.

## Core Resources

- UserAccount and AuthSession;
- ProfileSession;
- ResumeDocument;
- ParsedResumeReview;
- ProfileDraft;
- ConfirmedProfile;
- ResumeProfile library item;
- JobSearchRun and JobSearchTraceStep;
- SavedJob and SavedJobAnalysis.

The workflow session represents one resume-to-search path. Resume profiles and
saved jobs are durable user-library resources independent of a page visit.

## Profile State

Important ProfileSession.current_step values:

~~~text
created
resume_empty
resume_ready
resume_review
profile_draft
profile_confirmed
job_search_ready
job_search_running
job_search_completed
brief_ready
archived
~~~

The backend is the source of truth. Frontend route guards improve navigation;
backend ownership and state validation protect every operation.

Replacing an upstream resume must invalidate links to current downstream review,
draft, confirmed-profile, and search resources. Historical rows may remain for
audit but must not be treated as current. Expensive generation is idempotent by
default, and regeneration must be explicit.

## Search Execution

The fixed pipeline is:

~~~text
Search planning
-> Provider search
-> Candidate filtering
-> JD analysis
-> Profile matching
-> Result assembly
~~~

FastAPI persists a run and schedules in-process BackgroundTasks. JD analysis
uses a bounded per-run thread pool. This is an MVP execution model: work does
not survive process termination and concurrency is not coordinated across runs.

Trace steps preserve status, mode, fallback reason, warnings, duration, and
selected diagnostics. Traces are operational evidence, not a durable queue.

## Persistence

Local development uses sqlite3 and JOBAGENT_DB_PATH, defaulting to
data/jobagent.sqlite3. JSON snapshots preserve evolving profile, JD, and
analysis shapes.

init_database() creates tables, performs additive compatibility changes,
backfills ownership, and ensures indexes. This is acceptable for local MVP work
but is not the long-term migration mechanism.

Production direction:

- PostgreSQL and explicit versioned migrations;
- transactional ownership-sensitive writes;
- paginated queries;
- durable queue/worker execution;
- backup, retention, and recovery procedures.

## Refactoring Boundaries

app/application/job_search_usecases.py currently contains too many search
responsibilities. Refactor it incrementally:

1. Keep creation, authorization, run lifecycle, and high-level orchestration in
   the application layer.
2. Move each stage implementation behind a focused service or step runner.
3. Keep provider behavior in provider adapters.
4. Keep normalization, quality gates, and scoring testable without network or
   LLM calls.
5. Keep repository transactions out of prompts and provider code.

File size alone is not a refactoring requirement. Refactor when mixed ownership,
duplicated policy, or change risk makes the boundary valuable.

Do not restore deleted Streamlit, unversioned API, legacy LangGraph runtime, or
old tracker/import paths. Git history is the reference for removed code.
