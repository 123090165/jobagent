# V4 Frontend Route Guards

## Purpose

Vue route guards keep the user on the correct product step while the backend remains the source of truth.

No runtime behavior is implemented by this document.

## Rule

Before entering any session-based page:

```text
1. GET /api/v1/profile-sessions/{session_id}
2. check current_step
3. decide whether the page is allowed
4. redirect to the proper step if not allowed
```

Route guard logic belongs in `web/src/router` and the frontend store layer. It must not be implemented through backend templates.

## Recommended Mapping

```text
created / resume_empty:
  allowed: Home or Resume Intake
  redirect others to /

resume_ready:
  allowed: Resume Intake, Review
  redirect draft/confirmed/jobs to Review

resume_review:
  allowed: Review, Draft
  redirect confirmed/jobs to Draft

profile_draft:
  allowed: Draft, Confirmed
  redirect jobs to Confirmed

profile_confirmed / job_search_ready:
  allowed: Confirmed, Job Search

job_search_running / job_search_completed:
  allowed: Job Search, Job Detail, Brief

brief_ready:
  allowed: Brief, Job Search, Confirmed
```

## Frontend Error Handling

If `GET /api/v1/profile-sessions/{session_id}` returns `profile_session_not_found`, the frontend should show a recoverable user message and route back to Resume Intake.

If the backend returns `invalid_profile_session_state`, the frontend should refetch the session and rerun the guard before showing a blocking error.
