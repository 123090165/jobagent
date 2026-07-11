# Product Status And Roadmap

## Product Position

JobAgent is a local-first MVP with a complete happy path from resume intake to
analyzed and saved jobs. It is suitable for development and controlled private
testing. It is not ready to be exposed as a public multi-user service.

Implemented capabilities:

- username/password authentication and user-owned data;
- text and .txt/.md resume intake;
- deterministic parsing with optional LLM-assisted enrichment;
- user review, editable profile draft, and confirmed profile library;
- search preview, multiple providers, bounded candidate analysis, and traces;
- browser-assisted BOSS search and current-page capture;
- saved JD and analysis snapshots, tags, notes, and simple application status.
- user-visible search history, saved-job analysis history, and result feedback.

## Main Product Gap

The current flow produces job cards but does not close the outcome loop. There
is no reliable way to learn whether a result was relevant, whether the analysis
helped, or whether the user applied and received an interview.

The next milestone is a private beta centered on:

~~~text
Search history
-> inspect evidence
-> save or dismiss with a reason
-> track application state
-> generate job-specific actions
-> feed outcomes back into evaluation
~~~

Do not prioritize more agent frameworks or a large provider count before this
loop produces measurable user value.

## Delivery Priorities

### 1. Product Quality Loop

- Add user-visible search history and recovery.
- Add a saved-job detail view with analysis history.
- Record relevant, irrelevant, duplicate, stale, and insufficient-JD feedback.
- Track saved, interested, applied, interviewing, rejected, and closed states.
- Add Job Brief, resume-tailoring guidance, and interview preparation for a
  selected saved job.
- Add PDF and DOCX resume intake.
- Measure Top 5 relevance, save rate, dismiss reasons, apply rate, fallback
  rate, and provider detail coverage.

### 2. Production Boundary

- Require authentication outside an explicit local-development mode.
- Authenticate extension-to-backend calls.
- Add login throttling, data export/delete, privacy consent, and retention.
- Replace process-local background work before public deployment.
- Move production persistence to PostgreSQL with versioned migrations.

### 3. Scale And Recovery

- Add a durable job queue and independent workers.
- Support retry, cancellation, timeout, idempotency, stale-run recovery, and
  per-provider/global concurrency limits.
- Paginate user libraries and search history.
- Add structured logs, run correlation, provider metrics, and error monitoring.

### 4. Adaptive Workflow

Keep the current pipeline explicit while it remains fixed. Consider LangGraph
only when at least two of these are real requirements:

- automatic query rewriting loops;
- policy-driven provider fallback;
- user confirmation in the middle of a run;
- checkpoint/resume across dependent agent stages;
- later stages intentionally loop back to retrieval.

If adopted, orchestration must remain behind a JobAgent-owned interface. API and
repository contracts must not expose framework-specific types.

## Refactoring Decision

Use progressive refactoring. Do not perform a broad rewrite now, and do not
postpone all cleanup until feature development is finished.

Immediate rules:

- stop adding new responsibilities to job_search_usecases.py;
- keep current API and persistence behavior stable;
- extract a stage when the next feature materially changes that stage;
- schedule a short refactoring milestone before the next large search or Job
  Brief feature.

The first extraction should leave one readable orchestrator and focused modules
for planning, provider execution, candidate selection, JD analysis, matching,
and result assembly. Move behavior with tests; do not redesign all stages at
once.

The executable migration sequence and acceptance checks are defined in
[JOB_SEARCH_USECASE_REFACTOR_PLAN.md](JOB_SEARCH_USECASE_REFACTOR_PLAN.md).

Before public beta, address durable tasks, authentication mode, database
migrations, and data lifecycle as explicit architecture work.

## Non-Goals

- automatic applications without user confirmation;
- CAPTCHA or anti-bot bypass;
- sending browser cookies to the backend;
- fabricated resume evidence;
- distributed infrastructure before private-beta usage requires it.
