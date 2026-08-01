# Application Workbench

`SavedJob` is the user-owned canonical job record and the root of the job
workspace. It means the user explicitly operated on a job, not only that the
user bookmarked it. Search results remain transient until explicitly saved;
Browser Helper capture creates or updates the canonical job immediately.

Browser captures are source snapshots linked by `saved_job_id`. Analysis,
Chat context, communication drafts, tailored resumes, briefs, preparation, RAG
sync, and application tracking all refer to the canonical job. Repeated capture
of the same platform job or source URL updates one job workspace while retaining
separate capture snapshots for page-level audit and sending.

Each Saved Job may have one user-owned `JobApplication`. The application can be
created manually from the Saved Job page or by confirmed greeting delivery.
Merely saving a job, analyzing it, or generating a tailored resume does not
create application state.

The workbench returns the canonical job, current application, allowed stage
transitions, latest communication draft, latest tailored resume version, and an
append-only application event timeline. Saved Job archival remains library
organization; application stage is the only application-progress state.

The Web workbench presents one resource-derived current task instead of exposing
the internal `stage` and `next_action` values as primary controls. Browser Helper
actions update the same workspace, and the page refreshes it when the user returns
from the source listing. Progress completed outside JobAgent can be recorded as a
single user-reported stage without inventing intermediate events.

## Communication

Browser Helper reads the current job page only after a user click. A configured
LLM generates and reviews the greeting, with at most one content correction.
Failure creates no draft. Sending requires explicit confirmation,
operates on the visible BOSS composer, and updates the application to `contacted`
only after the exact sent text is visible on the page.

## Tailored Resume

Tailored versions are linked to one Saved Job and one source Resume Profile.
The JD decides which source-resume facts to emphasize but is never a candidate
fact source. The LLM returns a complete Markdown resume with an explicit
completion marker. The backend removes the marker and checks retained core
facts, newly introduced facts or placeholders, required sections, length, and
likely truncation. Blocking failures trigger at most one corrective generation;
continued failure creates no version.

Users may generate from the Saved Job Resume tab or from a user-triggered Browser
Helper capture. Editing reruns deterministic high-risk checks. New numbers,
dates, contacts, URLs, and placeholders block approval. Automated checks are a
guardrail, not a replacement for the user's factual review. Approved versions
are immutable, can be downloaded as an in-memory PDF, and require a new version
for further changes.

Automatic recruiter-message detection, background DOM polling, CDP monitoring,
conversation capture, and resume auto-send are outside the current boundary.
