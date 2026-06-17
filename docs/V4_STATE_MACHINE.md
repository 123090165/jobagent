# V4 State Machine

## Purpose

This document defines the v4 `ProfileSession` state machine, persistence timing, downstream invalidation, and idempotency rules.

No database code is implemented by this document. It is an architecture constraint for v4.1 and later implementation branches.

## Persistence Timing

The v4.0 in-memory repository is allowed only for the initial `/api/v1` skeleton and tests.

Starting in v4.1 Resume Intake, user workflow resources must be recoverable from backend persistence:

```text
ProfileSession
ResumeDocument
```

Recommended development default:

```text
database: SQLite
implementation style: existing sqlite3 repository pattern
```

Acceptance requirement for v4.1:

```text
If the backend process restarts, a created ProfileSession and its current ResumeDocument can be retrieved through /api/v1.
```

## Current Step Values

`ProfileSession.current_step` should use these values:

```text
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
```

## State Meanings

```text
created: session created but no resume yet
resume_empty: user attempted resume intake but no valid resume is stored
resume_ready: ResumeDocument exists and can be parsed
resume_review: ParsedResumeReview exists
profile_draft: ProfileDraft exists and can be edited
profile_confirmed: ConfirmedProfile exists
job_search_ready: confirmed profile can be used for job search
job_search_running: search run started
job_search_completed: search results available
brief_ready: at least one job brief generated
archived: no longer active
```

## Version Scope

```text
v4.1 supports at least: created, resume_ready
v4.2 adds: resume_review and a persisted ParsedResumeReview linked from ProfileSession.parsed_review_id
v4.3 adds: profile_draft
v4.4 adds: profile_confirmed, job_search_ready
```

`resume_empty` is recommended for v4.1 validation feedback, but the backend may also return a validation error without persisting this state if no valid resume content exists.

In the current v4.4 implementation, confirming a profile draft stores `confirmed_profile_id` and moves the session directly to `job_search_ready`. The separate `profile_confirmed` state remains available for future UX refinements.

## Downstream Invalidation

When a user replaces the current `ResumeDocument`:

```text
- previous ParsedResumeReview must be invalidated
- previous ProfileDraft must be invalidated
- previous ConfirmedProfile must be invalidated
- previous JobSearchRun must not be reused as current result
- previous JobBrief must not be treated as current
- ProfileSession.current_step becomes resume_ready
```

Historical resources may be retained for audit or history views, but they must not remain linked as current workflow resources.

Recommended fields for persisted downstream resources:

```text
superseded_by
is_current
created_from_resume_document_id
```

## Idempotency and Regeneration

Expensive or LLM-related generation steps are idempotent by default:

```text
parse-resume
profile-draft
job brief
```

Default rule:

```text
If a current result already exists, return it.
Do not regenerate automatically.
```

Regeneration rule:

```text
Only regenerate when the user explicitly requests it.
API may support regenerate=true.
```

Examples:

```text
POST /api/v1/profile-sessions/{session_id}/parse-resume?regenerate=true
POST /api/v1/profile-sessions/{session_id}/profile-draft?regenerate=true
POST /api/v1/job-search-runs/{run_id}/brief?regenerate=true
```
