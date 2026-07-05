# API Contract V1

`/api/v1` is the only current public product API surface for the Vue frontend in
`web/`.

The frontend must call HTTP endpoints and must not import backend services.

## Current Product Flow

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

## Implemented Resources

### ProfileSession

Primary workflow resource for one resume-to-job-search flow.

Linked current-resource ids:

- `resume_document_id`
- `parsed_review_id`
- `profile_draft_id`
- `confirmed_profile_id`

Important `current_step` values include:

- `created`
- `resume_empty`
- `resume_ready`
- `resume_review`
- `profile_draft`
- `job_search_ready`
- `job_search_running`
- `job_search_completed`
- `brief_ready`
- `archived`

### ResumeDocument

Uploaded or pasted resume input linked from a `ProfileSession`.

### ParsedResumeReview

Structured resume review generated from a `ResumeDocument`.

### ProfileDraft

Editable search-ready draft generated from a parsed review.

### ConfirmedProfile

User-confirmed, search-ready profile.

### JobSearchRun

Tracked job-search execution created from a confirmed profile.

The current search pipeline records trace steps for:

- Search planning
- Provider search
- Candidate filtering
- JD analysis
- Profile matching
- Result assembly

### BrowserJobCapture

User-triggered browser job-detail input. It captures visible page text and page
metadata from a Chrome/Edge extension, then maps that input into the existing
JobSearchRun analysis pipeline.

### JobBrief

Next planned v4.6 resource. It is not implemented in the current API yet.

## Implemented Routes

### Profile Session And Resume Intake

```text
POST /api/v1/profile-sessions
GET  /api/v1/profile-sessions/{session_id}
POST /api/v1/profile-sessions/{session_id}/resume-text
POST /api/v1/profile-sessions/{session_id}/resume-file
GET  /api/v1/profile-sessions/{session_id}/resume
```

### Resume Review

```text
POST /api/v1/profile-sessions/{session_id}/parse-resume
GET  /api/v1/profile-sessions/{session_id}/parsed-review
```

`parse-resume` accepts query flags:

- `regenerate`
- `use_llm`

### Profile Draft

```text
POST  /api/v1/profile-sessions/{session_id}/profile-draft
GET   /api/v1/profile-drafts/{draft_id}
PATCH /api/v1/profile-drafts/{draft_id}
POST  /api/v1/profile-drafts/{draft_id}/confirm
```

`profile-draft` accepts `regenerate`.

### Confirmed Profile

```text
GET /api/v1/confirmed-profiles/{confirmed_profile_id}
```

### Job Search

```text
POST /api/v1/job-search-runs
GET  /api/v1/job-search-runs/{run_id}
GET  /api/v1/job-search-runs/{run_id}/steps
GET  /api/v1/profile-sessions/{session_id}/job-search-runs
```

`POST /api/v1/job-search-runs` accepts:

```json
{
  "session_id": "uuid",
  "search_mode": "live_search",
  "search_provider": "cuhksz_career",
  "use_llm": false,
  "locations": [],
  "target_roles": [],
  "keywords": [],
  "max_results": 10
}
```

Supported providers:

- `mock`
- `cuhksz_career`

### Browser Job Capture

```text
POST /api/v1/browser/job-captures/analyze
```

Request:

```json
{
  "session_id": "uuid",
  "source": "company_site",
  "source_url": "https://jobs.example.com/backend-intern",
  "page_title": "Backend Engineer Intern - Example",
  "title": "Backend Engineer Intern",
  "company": "Example",
  "location": "Remote",
  "salary": null,
  "jd_text": "visible job description text...",
  "visible_text": "optional visible page text...",
  "captured_at": "2026-07-05T00:00:00Z",
  "extractor_version": "browser-helper-current-page-v1",
  "warnings": [],
  "use_llm": false
}
```

Response:

```json
{
  "capture": {
    "source": "company_site",
    "source_url": "https://jobs.example.com/backend-intern",
    "page_title": "Backend Engineer Intern - Example",
    "title": "Backend Engineer Intern",
    "company": "Example",
    "location": "Remote",
    "salary": null,
    "jd_text_preview": "visible job description text...",
    "captured_at": "2026-07-05T00:00:00Z",
    "extractor_version": "browser-helper-current-page-v1"
  },
  "report": {
    "overall_score": 80,
    "recommendation": "Worth reviewing closely and tailoring before applying.",
    "matched_strengths": [],
    "critical_gaps": [],
    "resume_actions": [],
    "interview_questions": [],
    "confidence_label": "medium",
    "analysis_mode": "mock"
  },
  "warnings": [],
  "job_search_run_id": "uuid",
  "job_result_id": "uuid"
}
```

This endpoint requires an existing ProfileSession with a confirmed profile. It
does not create an application record. It persists the underlying JobSearchRun
because that is the existing analysis record for the v4 flow.

### Provider And LLM Status

```text
GET /api/v1/job-search-providers/status
GET /api/v1/llm/status
```

Provider status accepts optional `provider`.

## Planned v4.6 Job Brief Routes

```text
POST /api/v1/job-search-runs/{run_id}/results/{result_id}/brief
GET  /api/v1/job-briefs/{brief_id}
```

The brief resource should be tied to:

- `job_search_run_id`
- `job_result_id`
- `confirmed_profile_id`

## Error Contract

All product-flow errors use:

```json
{
  "detail": "Human readable error message",
  "error_code": "machine_readable_error_code"
}
```

See `docs/V4_ERROR_CONTRACT.md` for frontend handling guidance.
