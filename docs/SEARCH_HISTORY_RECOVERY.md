# Search History And Recovery

## Current Behavior

- `GET /api/v1/job-search-runs` lists the current user's most recently updated
  runs across all resume profile sessions.
- History entries can reopen a persisted run without repeating provider or LLM
  work.
- Reopening a pending or running run restarts frontend polling. Completed and
  failed runs remain inspectable after refresh, logout, and login.
- Each live run stores the bounded, deduplicated provider candidate pool in
  user-scoped `job_search_items` as soon as recall completes. Final scored
  `JobSearchRun.results` remain a separate backward-compatible Top N projection.
- `GET /api/v1/job-search-runs/{run_id}/items` reads the persisted candidate
  pool without inflating the existing run and history responses.
- Candidate persistence never creates a Saved Job. Saving remains an explicit
  user action on a final scored result.
- A user cannot list or open another user's runs.

## Recovery Boundary

The current recovery is client and persistence recovery, not worker recovery.
FastAPI background tasks run in the API process. If that process exits during a
search, the persisted run may remain pending or running and cannot continue from
its last trace step.

Durable execution recovery requires the roadmap's queue and worker milestone:
idempotent stage execution, leases or heartbeats, stale-run detection, retry,
cancellation, and checkpointed inputs. The history UI must not imply that simply
opening an interrupted run resumes backend work.

## Acceptance Checks

- History is ordered by most recent update and is scoped to the authenticated
  user.
- Status, query, provider, result count, and timestamps are visible.
- Opening a completed run does not create a new run.
- Opening an active run resumes polling.
- Search again returns to the original profile session's preview page.
- Re-executing a run replaces its recalled pool idempotently, final result
  snapshots attach to matching candidate rows, and deleting the run deletes its
  candidate rows without deleting Saved Jobs.
