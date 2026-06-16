# JobAgent v4 Product Refactor Plan

Imported from the v4 product refactor planning note on 2026-06-15.

## 0. Purpose

JobAgent is moving from a Streamlit-based prototype into a clearer product-oriented architecture.

The goal is not to blindly replace Streamlit with Vue 3, nor to rewrite the entire project at once. The goal is to make the project clean, maintainable, and product-ready by separating responsibilities:

```text
FastAPI backend = business logic and workflow state
Vue 3 frontend = user-facing product interaction
Streamlit = legacy demo/admin/debug panel
```

Every future step must be small, testable, and reviewed before continuing.

## 1. Current Situation

JobAgent has already validated several MVP capabilities:

```text
- Resume upload / paste input in Streamlit
- Resume parsing review
- Search-ready profile draft generation
- Editable ProfileDraft
- ConfirmedProfile flow
- Ollama as default local model provider
- DeepSeek as optional provider
- Basic /api/v1 ProfileSession skeleton
- Initial Vue 3 shell under web/
```

However, the current architecture has several problems:

```text
1. Streamlit is acting as both frontend and workflow coordinator.
2. Streamlit code directly imports backend services.
3. User-facing state is stored in Streamlit session_state.
4. The product flow is exposed as multiple tool tabs instead of a guided journey.
5. Backend APIs are partly function-oriented instead of resource-oriented.
6. Future features such as multi-user state, history recovery, job search, and reports need clearer backend resources.
```

Therefore, v4 should reorganize the project around a clean product workflow.

## 2. Product Goal

From a normal user's perspective, JobAgent should feel like this:

```text
I upload or paste my resume.
JobAgent understands my background.
I confirm or correct the parsed information.
JobAgent builds a search-ready profile.
I confirm the final profile.
JobAgent searches jobs based on that profile.
JobAgent explains which jobs match, why they match, and how I should apply.
```

The target user journey is:

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

This flow should be visible in the frontend as a guided step-by-step experience, not as unrelated tabs.

## 3. Architecture Decision

The long-term architecture should be:

```text
jobagent/
  app/          # FastAPI backend
  web/          # Vue 3 user-facing frontend
  frontend/     # legacy Streamlit demo/admin panel
  tests/
  docs/
```

### 3.1 app/

`app/` is the only place for business logic.

Responsibilities:

```text
- ProfileSession lifecycle
- ResumeDocument storage
- resume file/text ingestion
- resume parsing
- ParsedResumeReview generation
- ProfileDraft generation and update
- ConfirmedProfile creation
- JobSearchRun creation
- JobBrief generation
- LLM provider orchestration
- persistence
- validation
```

### 3.2 web/

`web/` is the formal user-facing frontend.

Responsibilities:

```text
- pages
- components
- routing
- forms
- upload controls
- editable cards
- API calls
- user feedback
- frontend-only UI state
```

The Vue frontend must not import Python backend services.

### 3.3 frontend/

`frontend/` keeps the existing Streamlit implementation, but only as:

```text
legacy demo/admin/debug panel
```

It should not continue receiving new user-facing product features.

## 4. Non-Negotiable Design Rules

### Rule 1: Frontend must not import backend services

Bad:

```python
from app.services.profile_draft_service import create_profile_draft
```

Good:

```ts
await api.post("/api/v1/profile-sessions/{id}/profile-draft")
```

### Rule 2: Backend workflow state must be resource-based

Do not rely on frontend memory/session state as the source of truth.

The backend should own:

```text
ProfileSession.current_step
resume_document_id
parsed_review_id
profile_draft_id
confirmed_profile_id
```

From v4.1 onward, user workflow resources must be recoverable from backend persistence. The v4.0 in-memory repository is allowed only for the initial skeleton and tests.

### Rule 3: One step per branch

Each Codex iteration should implement only one product step.

### Rule 4: No feature expansion inside refactor branches

Do not mix architecture refactor with:

```text
- JD search
- resume optimization
- interview challenge
- login
- PDF/DOCX/OCR
- vector database
- complex deployment
```

unless that step explicitly targets it.

### Rule 5: Every step needs tests and acceptance criteria

Each branch must return:

```text
branch:
commit:
changed files:
tests:
manual_acceptance:
status:
notes:
```

### Rule 6: Expensive generation is idempotent by default

LLM-backed or otherwise expensive steps must return the current result if one already exists. They must not regenerate automatically.

Regeneration requires an explicit user action and may be represented with `regenerate=true`.

### Rule 7: Downstream resources must be invalidated after upstream replacement

If a user replaces the current resume, all downstream resources created from the previous resume must stop being treated as current.

Historical resources may be retained, but they must be marked as stale or superseded.

## 5. Core Backend Resources

The v4 product flow should be organized around these resources:

```text
ProfileSession
ResumeDocument
ParsedResumeReview
ProfileDraft
ConfirmedProfile
JobSearchRun
JobBrief
```

Relationship:

```text
ProfileSession
  |-- ResumeDocument
  |-- ParsedResumeReview
  |-- ProfileDraft
  `-- ConfirmedProfile
        `-- JobSearchRun
              `-- JobBrief
```

The most important resource is `ProfileSession`.

It represents one user's profile-building workflow.

## 6. ProfileSession State Machine

Suggested states:

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

Early v4 only needs:

```text
v4.1: created, resume_ready
v4.2: resume_review
v4.3: profile_draft
v4.4: profile_confirmed, job_search_ready
```

State transitions:

```text
create session
-> created

submit resume text/file
-> resume_ready with resume_document_id

empty or invalid resume intake attempt
-> resume_empty

parse resume
-> resume_review with parsed_review_id

generate profile draft
-> profile_draft with profile_draft_id

confirm profile
-> job_search_ready with confirmed_profile_id

start job search
-> job_search_running / job_search_completed
```

See `docs/V4_STATE_MACHINE.md` for the authoritative v4 state, persistence, and invalidation rules.

## 7. API Contract Direction

The target `/api/v1` contract should eventually include:

### Profile Session

```text
POST /api/v1/profile-sessions
GET  /api/v1/profile-sessions/{session_id}
```

### Resume Intake

```text
POST /api/v1/profile-sessions/{session_id}/resume-text
POST /api/v1/profile-sessions/{session_id}/resume-file
GET  /api/v1/profile-sessions/{session_id}/resume
```

### Resume Review

```text
POST /api/v1/profile-sessions/{session_id}/parse-resume
POST /api/v1/profile-sessions/{session_id}/parse-resume?regenerate=true
GET  /api/v1/profile-sessions/{session_id}/parsed-review
```

### Profile Draft

```text
POST  /api/v1/profile-sessions/{session_id}/profile-draft
POST  /api/v1/profile-sessions/{session_id}/profile-draft?regenerate=true
GET   /api/v1/profile-drafts/{draft_id}
PATCH /api/v1/profile-drafts/{draft_id}
POST  /api/v1/profile-drafts/{draft_id}/confirm
```

### Job Search

```text
POST /api/v1/job-search-runs
GET  /api/v1/job-search-runs/{run_id}
```

### Job Brief

```text
POST /api/v1/job-search-runs/{run_id}/brief
POST /api/v1/job-search-runs/{run_id}/brief?regenerate=true
GET  /api/v1/briefs/{brief_id}
```

All `/api/v1` errors should follow the unified format in `docs/V4_ERROR_CONTRACT.md`.

## 8. Frontend Product Pages

The Vue frontend should eventually use route-based pages:

```text
/                         Home / Resume Intake
/profile/:sessionId/review
/profile/:sessionId/draft
/profile/:sessionId/confirmed
/jobs/search
/jobs/:runId
/briefs/:briefId
/history
```

Do not use the old Streamlit tab structure as the user-facing product model.

Session-based pages must fetch `ProfileSession` before entering the page and redirect according to `current_step`. See `docs/V4_FRONTEND_ROUTE_GUARDS.md`.

## 9. Iteration Roadmap

### v4.0 - Architecture Baseline

Status: started.

Goal:

```text
- Add /api/v1 skeleton
- Define ProfileSession
- Create Vue 3 shell
- Mark Streamlit as legacy demo/admin
```

Acceptance criteria:

```text
- POST /api/v1/profile-sessions works
- GET /api/v1/profile-sessions/{session_id} works
- Vue 3 shell exists under web/
- Streamlit is documented as legacy
- Python tests pass
- Vue build passes before merge
```

Required checks:

```powershell
.venv\Scripts\python.exe -m pytest
cd web
npm install
npm run build
```

### v4.1 - Resume Intake Flow

Status: implemented.

Goal:

Make the Vue homepage usable for the first real user action.

User can:

```text
- create a ProfileSession
- upload a txt/md resume
- paste resume text
- submit resume content to the backend
- continue to /profile/:sessionId/review
```

Backend scope:

```text
- ResumeDocument schema
- ResumeDocument repository
- minimal SQLite persistence for ProfileSession and ResumeDocument
- POST /api/v1/profile-sessions/{session_id}/resume-text
- POST /api/v1/profile-sessions/{session_id}/resume-file
- update ProfileSession.resume_document_id
- update ProfileSession.current_step = resume_ready after valid resume intake
- invalidate stale downstream resources if resume input is replaced
```

Frontend scope:

```text
- enable Upload resume
- enable Paste resume
- show resume text preview
- show upload errors in user-friendly language
- call backend APIs only
- route to review page after successful resume intake
```

Do not do:

```text
- resume parsing
- profile draft generation
- job search
```

Acceptance criteria:

```text
- ProfileSession and ResumeDocument are persisted and recoverable
- upload txt works
- upload md works
- paste text works
- GET /api/v1/profile-sessions/{session_id}/resume returns the current ResumeDocument
- unsupported file shows clear error
- empty file/text shows clear error
- frontend never imports backend service
- backend tests pass
- Vue build passes
```

### v4.2 - Resume Review Flow

Status: implemented.

Goal:

Parse the resume and let the user confirm whether JobAgent understood the resume correctly.

Backend scope:

```text
- ParsedResumeReview schema
- ParsedResumeReview repository
- POST /api/v1/profile-sessions/{session_id}/parse-resume
- GET /api/v1/profile-sessions/{session_id}/parsed-review
- reuse existing parser/service behind an application usecase
```

Frontend scope:

```text
- /profile/:sessionId/review page
- call parse-resume API
- show parsed result as cards, not raw JSON
- sections:
  - basic info
  - education
  - skills
  - projects
  - work experience
  - warnings
  - missing info questions
- allow user to continue to profile draft
```

Do not do:

```text
- full editing of ProfileDraft
- job search
```

Acceptance criteria:

```text
- user can trigger resume parsing
- parsed review is persisted or retrievable
- page displays human-readable cards
- raw JSON may exist only under debug/details
- backend tests pass
- Vue build passes
```

### v4.3 - Profile Draft Generation and Editing

Goal:

Generate a search-ready profile draft from ParsedResumeReview and allow user editing.

Backend scope:

```text
- ProfileDraft API under /api/v1
- POST /api/v1/profile-sessions/{session_id}/profile-draft
- GET /api/v1/profile-drafts/{draft_id}
- PATCH /api/v1/profile-drafts/{draft_id}
- reuse existing profile draft service behind application usecase
```

Frontend scope:

```text
- /profile/:sessionId/draft page
- editable summary
- editable target directions
- editable core skills
- editable auxiliary skills
- editable search keywords
- editable preferred locations
- editable work arrangements
- save draft changes through API
```

Acceptance criteria:

```text
- user can generate draft
- user can edit fields
- user can save edits
- backend stores updated draft
- ProfileSession.current_step = profile_draft
- backend tests pass
- Vue build passes
```

### v4.4 - Confirmed Profile

Goal:

User confirms the final search-ready profile.

Backend scope:

```text
- ConfirmedProfile schema/resource
- POST /api/v1/profile-drafts/{draft_id}/confirm
- update ProfileSession.confirmed_profile_id
- update ProfileSession.current_step = job_search_ready
```

Frontend scope:

```text
- /profile/:sessionId/confirmed page
- show final confirmed profile summary
- show target directions and search keywords
- button: Back to Edit
- button: Start Job Search
```

Acceptance criteria:

```text
- user can confirm profile
- confirmed profile is stored
- session enters job_search_ready
- confirmed page is available in Vue
- job search remains a later step
- backend tests pass
- Vue build passes
```

### v4.5a - Local/Mock Job Search

Goal:

Search jobs based on ConfirmedProfile using local or mock data first.

Backend scope:

```text
- JobSearchRun schema/resource
- POST /api/v1/job-search-runs
- GET /api/v1/job-search-runs/{run_id}
- require confirmed_profile_id
- generate search query from ConfirmedProfile
```

Frontend scope:

```text
- /jobs/search
- show recommended search keywords from confirmed profile
- allow user to edit keywords, location, job type
- show job result cards
```

Acceptance criteria:

```text
- job search requires confirmed profile
- search returns job cards
- each job card includes title, company, location, match summary
- backend tests pass
- Vue build passes
```

### v4.5b - Imported JD Search

Goal:

Search or rank user-imported JD content after the local/mock job search product shape is stable.

### v4.5c - Live Provider Search

Goal:

Connect live providers only after local/mock result cards and match explanations are stable.

### v4.6 - Job Brief

Goal:

Generate a detailed explanation for a selected job.

Backend scope:

```text
- JobBrief schema/resource
- POST /api/v1/job-search-runs/{run_id}/brief
- GET /api/v1/briefs/{brief_id}
```

Frontend scope:

```text
- /briefs/:briefId
- show JD summary
- match reasons
- gap analysis
- resume improvement suggestions
- interview challenge points
- application recommendation
```

Acceptance criteria:

```text
- user can generate brief
- brief is tied to job search run and confirmed profile
- brief is displayed as structured sections
- backend tests pass
- Vue build passes
```

### v4.7 - Streamlit Cleanup

Goal:

Finalize Streamlit as legacy demo/admin.

Scope:

```text
- update docs
- remove user-facing positioning from Streamlit
- keep only debug/demo/admin use cases
- avoid adding new product features to Streamlit
```

Acceptance criteria:

```text
- docs clearly state web/ is user-facing frontend
- frontend/ is legacy demo/admin
- new product flow is Vue + FastAPI
```

## 10. Testing Policy

Every backend-changing branch must run:

```powershell
.venv\Scripts\python.exe -m py_compile <changed python files>
.venv\Scripts\python.exe -m pytest <relevant tests>
.venv\Scripts\python.exe -m pytest
```

Every `web/`-changing branch must run:

```powershell
cd web
npm install
npm run build
```

If dependencies are not installed, the branch is not ready to merge into main.

## 11. Manual Acceptance Policy

Every product-flow branch must include manual acceptance notes.

Example:

```text
manual_acceptance:
- Opened Vue homepage
- Created profile session
- Uploaded txt resume
- Pasted resume text
- Saw user-friendly error for empty input
- Navigated to review page
```

Do not merge if manual acceptance is not run for user-facing frontend changes.

## 12. Branching Policy

Suggested branches:

```text
codex/v4-api-contract-and-vue3-shell
codex/v4-resume-intake-flow
codex/v4-resume-review-flow
codex/v4-profile-draft-flow
codex/v4-confirmed-profile-flow
codex/v4-job-search-flow
codex/v4-job-brief-flow
```

One branch per step.

## 13. Scope Control

Do not combine unrelated work.

Bad example:

```text
Resume Intake + PDF parsing + JD search + UI redesign
```

Good example:

```text
Resume Intake only
```

Each step should leave the project in a runnable, testable state.

## 14. Current Next Action

Before starting v4.1, verify v4.0:

```powershell
cd web
npm install
npm run build
```

If build passes, merge v4.0.

Then start:

```text
v4.1 Resume Intake Flow
```

The goal of v4.1 is:

```text
Vue homepage can create a profile session, upload or paste resume content, store it as ResumeDocument, and continue to the review page.
```

## 15. Hardening References

- `docs/V4_STATE_MACHINE.md`
- `docs/V4_ERROR_CONTRACT.md`
- `docs/V4_FRONTEND_ROUTE_GUARDS.md`
