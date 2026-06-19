# Cleanup Audit

Audit date: 2026-06-19.

## Current Mainline Architecture

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

Current runtime:

- backend: `app/`
- API: `app/api/v1`
- frontend: `web/`
- providers: `mock`, `cuhksz_career`

## Deleted Runtime Areas

- Streamlit `frontend/`
- old unversioned FastAPI routes
- old workflow/LangGraph runtime
- old workflow-only agents
- old ApplicationRecord tracker flow
- old JobImportCandidate flow
- old provider paths for `local_db`, `gemini_cli`, and `cuhksz_live`
- old demo/evaluation scripts

## Deleted Docs

Docs centered on deleted runtime paths were removed, including old API,
architecture, storage, agent, Streamlit, workflow, tracker/import, old provider,
and demo/evaluation docs.

## Dependency Findings

Removed:

- `streamlit`
- `langgraph`
- `requests`

Kept:

- `beautifulsoup4`: current CUHKSZ provider parsing
- `httpx`: FastAPI/Starlette test client
- `python-multipart`: upload endpoints

## Docs Classification

| Doc | Classification | Notes |
| --- | --- | --- |
| `README.md` | keep | Project entry point. |
| `docs/INDEX.md` | rewrite | Canonical docs entry point added in this pass. |
| `docs/API_CONTRACT_V1.md` | rewrite | Current route contract. |
| `docs/V4_PRODUCT_REFACTOR_PLAN.md` | rewrite | Current product plan. |
| `docs/SEARCH_PROVIDER.md` | rewrite | Current provider architecture. |
| `docs/NEXT_DEV_PLAN.md` | rewrite | v4.6 plan added in this pass. |
| `docs/CLEANUP_AUDIT.md` | rewrite | Cleanup record. |
| `docs/LEGACY_MAP.md` | rewrite | Removed legacy map. |
| `docs/V4_STATE_MACHINE.md` | keep | State rules. |
| `docs/V4_ERROR_CONTRACT.md` | keep | Error rules. |
| `docs/V4_FRONTEND_ROUTE_GUARDS.md` | keep | Frontend routing rules. |
| `docs/CONFIRMED_PROFILE_PERSISTENCE.md` | keep | Current persistence detail. |
| `docs/LLM_ASSISTED_PROFILE_ENRICHMENT.md` | keep | Current enrichment behavior. |
| `docs/LLM_PROMPT_AND_QUALITY_CONTROL.md` | keep | Current LLM safety guidance. |
| `docs/PROFILE_FLOW_DECOUPLING.md` | keep | Current flow decoupling context. |
| `docs/PROFILE_REVIEW_QUALITY_EVALUATION.md` | keep | Current evaluation notes. |
| `docs/SEARCH_READY_PROFILE_LAYER.md` | keep | Current profile layer. |
| `docs/SECTION_BASED_RESUME_PARSER.md` | keep | Current parser design. |
| `docs/GIT_WORKFLOW.md` | rewrite | Current development process. |
| `docs/API.md` | delete | Deleted legacy unversioned API doc. |
| `docs/ARCHITECTURE.md` | delete | Deleted legacy Streamlit/workflow architecture doc. |
| `docs/ARCHITECTURE_OVERVIEW.md` | delete | Deleted legacy mixed-era architecture overview. |
| `docs/STORAGE.md` | delete | Deleted legacy analysis-record storage doc. |
| `docs/AGENTS.md` | delete | Deleted legacy workflow-agent doc. |
| `docs/AGENT_BOUNDARIES.md` | delete | Deleted legacy workflow-agent boundary doc. |
| `docs/AGENT_TRACE.md` | delete | Deleted legacy workflow-trace doc. |
| `docs/DATA_SCHEMA.md` | delete | Deleted legacy schema overview. |
| `docs/DECISIONS.md` | delete | Deleted legacy decision log. |
| `docs/DEVELOPMENT_REVIEW_GUIDE.md` | delete | Deleted legacy development guide. |
| `docs/EXAMPLE_PROJECTS.md` | delete | Deleted old portfolio/example planning doc. |
| `docs/FRONTEND_SEPARATION_PLAN.md` | delete | Deleted Streamlit separation plan after Streamlit removal. |
| `docs/HELLO_AGENTS_NOTES.md` | delete | Deleted legacy agent notes. |
| `docs/JD_QUALITY_GATE.md` | delete | Deleted old provider/JD quality doc. |
| `docs/JD_URL_IMPORT.md` | delete | Deleted old unversioned import route doc. |
| `docs/LLM_INTEGRATION.md` | delete | Deleted legacy workflow-agent LLM doc. |
| `docs/PORTFOLIO_PITCH.md` | delete | Deleted old portfolio pitch. |
| `docs/PRD.md` | delete | Deleted old PRD superseded by v4 docs. |
| `docs/PROFILE_DRAFT_EDITING_UI.md` | delete | Deleted old UI doc superseded by v4 flow docs. |
| `docs/REFERENCES.md` | delete | Deleted old research/reference notes. |
| `docs/RESUME_FILE_PARSER.md` | delete | Deleted old unversioned route parser doc. |
| `docs/RESUME_PROFILE_PARSER_EVALUATION.md` | delete | Deleted old evaluation-script doc. |
| `docs/ROADMAP.md` | delete | Deleted old roadmap superseded by next dev plan. |
| `docs/SCREENSHOT_GUIDE.md` | delete | Deleted old screenshot guide. |
| `docs/SLATE_LIKE_PROFILE_REVIEW_UI.md` | delete | Deleted old Streamlit UI doc. |
| `docs/V4_ARCHITECTURE_PLAN.md` | delete | Deleted overlapping architecture plan merged into index/product plan. |

## Recommended Next Cleanup

Review remaining supporting docs periodically and merge any repeated information
into `docs/INDEX.md`, `docs/API_CONTRACT_V1.md`, or `docs/NEXT_DEV_PLAN.md`.
