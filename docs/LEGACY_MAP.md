# Legacy Map

The old runtime paths have been deleted. This file exists only to identify what
was removed and to prevent accidental restoration.

## Removed Legacy Areas

- Streamlit `frontend/`
- old unversioned API routes under `app/api/routes_*.py`
- old full-analysis workflow under `app/workflows/`
- old workflow-only agents: MatchAgent, ResumeOptimizeAgent,
  ProjectChallengeAgent, ReportAgent, and MissingInfoAgent
- old ApplicationRecord tracker flow
- old JobImportCandidate flow
- old `/search/jobs` provider stack
- old providers: `local_db`, `gemini_cli`, `cuhksz_live`
- old public job storage service
- old demo/evaluation scripts
- old docs for the deleted systems

## Removed Dependencies

- `streamlit`
- `langgraph`
- `requests`

## Current Mainline

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

Runtime:

- backend: `app/`
- public API: `app/api/v1`
- frontend: `web/`
- providers: `mock`, `cuhksz_career`

## Remaining Legacy Risk

No known live legacy runtime path remains from the removed systems.

The main risk is documentation drift. Use `docs/INDEX.md` as the canonical docs
entry point and avoid restoring deleted old-flow docs as active architecture.
