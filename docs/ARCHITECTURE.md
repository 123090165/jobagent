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
- web/src/composables: page-level controls and browser-session coordination;
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

Candidate filtering produces a `recall_score` from title, snippet, source, and
basic profile fit. JD analysis then preserves the full description and extracts
typed requirements with required/preferred/unknown necessity and grounded JD
quotes. Profile matching builds one `JobMatchContext` per candidate, re-checks
hard constraints against the enriched JD, and produces `final_match_score`, key
evidence, and unknowns. Search cards display that final score. Saving a search
result persists the same requirements and analysis snapshot; a later Job Brief
explains that saved analysis rather than replacing the search score.
Repeated saves append `SavedJobAnalysis` history and move `latest_analysis` to
the newest snapshot. The Saved Job's current JD and structured fields are
refreshed only with richer incoming content, so shorter snippets cannot replace
a previously captured full description.

FastAPI persists a run and schedules in-process BackgroundTasks. JD analysis
uses a bounded per-run thread pool. This is an MVP execution model: work does
not survive process termination and concurrency is not coordinated across runs.

Trace steps preserve status, mode, fallback reason, warnings, duration, and
selected diagnostics. Traces are operational evidence, not a durable queue.

## Career Assistant

The persistent chat assistant is a read-only consumer of profile, search, and
saved-job resources. It is not a seventh Search V2 stage and does not alter the
search pipeline or its trace contract.

Each turn follows a bounded agent and retrieval flow:

~~~text
owned conversation state
-> compact context manifest
-> answer agent selects read-only tools or answers directly
-> deterministic minimum-context policy
-> reference resolver
-> server-side ownership checks
-> optional typed resource retrieval (one bounded tool round)
-> grounded answer with validated citations
-> persisted turn
-> optional derived-memory compaction
~~~

The compact manifest contains labels and source types for pinned context and
previous references; it contains no
executable resource IDs or raw JD bodies. The same answer agent may answer
ordinary questions directly or request a bounded set of read-only tools. A
deterministic minimum-context policy supplements obvious fit, comparison,
pinned-context, and follow-up needs so an agent omission cannot silently hide
available evidence. The resolver chooses only among `use_attachment`,
`reuse_previous`, `use_pinned`, and `load_recent`; repositories then enforce the
current `user_id` ownership. Raw resume text is excluded from assistant context.

There is no separate LLM router call. The persisted route is derived from the
agent's actual tool selection and the enforced retrieval plan for compatibility
and diagnostics. Ordinary questions may receive a direct answer without
personal-data retrieval. Only the deterministic hard safety gate produces
`refused`. Conversation commands such as retrying the previous question are
resolved before the agent step while the original user message remains in chat
history.

`chat_turns` retains the original question and answer until user deletion. It
also retains bounded original attachment selectors and optional retry lineage
so a fallback can be retried without relying on natural-language command
recognition or copying resource bodies.
Conversation summaries are rebuildable navigation memory and never replace raw
turns or current profile/job evidence. Deleting a turn invalidates derived
summary state; clearing memory removes all turns, summaries, citations, and
last-retrieval state while retaining an empty conversation shell.

Conversations are global user resources rather than children of a Profile,
Search Run, or Saved Job route. Resource pages may create a global conversation
with pinned context, and users can later adjust or clear that context through
the Assistant workspace. This permits cross-resource comparisons without
coupling conversation lifetime to page navigation.

The Assistant memory panel is a derived view over the owned conversation,
turns, summary metadata, pinned resource IDs, and latest citations. It does not
introduce a second store for Profile, job-description, or search-result data.
Failure to build this auxiliary view does not block loading chat history or
creating a new answer.

## MCP Service Integrations

Optional MCP services remain separate runtime processes. JobAgent owns the
backend-side client, static tool allowlist, timeouts, response budgets, and
typed adapters; the external service owns its retrieval implementation,
dependencies, and storage.

The Modular RAG integration currently provides service discovery and typed,
allowlisted calls for collection listing, knowledge retrieval, and document
summaries. It is not part of Search V2 and its tools are not exposed to the
Career Assistant or another LLM without a separate product-policy integration.
An unavailable optional MCP service does not prevent JobAgent from starting.
See `MODULAR_RAG_MCP.md`.

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

## Search Module Boundaries

app/application/job_search_usecases.py owns authorization, run lifecycle, and
high-level orchestration. Stage behavior lives behind focused service modules:

1. app/services/job_search_planner.py owns intent-to-plan assembly.
2. app/services/job_search_execution/ owns preview, provider execution,
   candidate analysis, result assembly, and trace helpers.
3. app/services/job_candidate_filter.py coordinates candidate selection behind
   the filter_candidates() facade; job_candidate_constraints.py,
   job_candidate_scoring.py, and job_candidate_reranker.py own the three
   deterministic constraint, scoring, and bounded LLM stages.
4. app/services/job_search_providers/ owns source-specific provider behavior.
5. repositories own persistence and must remain outside prompts and provider
   adapters.

New search work should extend the module that owns its stage instead of moving
policy back into the application orchestrator. File size alone is not a
refactoring requirement; split a module when mixed ownership, duplicated policy,
or change risk makes the boundary valuable.

Do not restore deleted Streamlit, unversioned API, legacy LangGraph runtime, or
old tracker/import paths. Git history is the reference for removed code.
