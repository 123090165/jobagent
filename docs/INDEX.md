# JobAgent Docs Index

## Current product flow

Resume Intake -> Resume Review -> Profile Draft -> Confirmed Profile -> Job Search -> Job Brief

## Canonical docs

- [README.md](../README.md)
- [docs/API_CONTRACT_V1.md](API_CONTRACT_V1.md)
- [docs/PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- [docs/V4_PRODUCT_REFACTOR_PLAN.md](V4_PRODUCT_REFACTOR_PLAN.md)
- [docs/SEARCH_PROVIDER.md](SEARCH_PROVIDER.md)
- [docs/NEXT_DEV_PLAN.md](NEXT_DEV_PLAN.md)
- [docs/CLEANUP_AUDIT.md](CLEANUP_AUDIT.md)
- [docs/DELETED_FILES_2026_06_25.md](DELETED_FILES_2026_06_25.md)
- [docs/LEGACY_MAP.md](LEGACY_MAP.md)

## Current architecture

- backend: `app/`
- API: `app/api/v1`
- frontend: `web/`
- providers: `mock`, `cuhksz_career`

## Next development plan

v4.6 Job Brief

See [docs/NEXT_DEV_PLAN.md](NEXT_DEV_PLAN.md).

## Removed legacy areas

- Streamlit `frontend/`
- old unversioned API routes
- old workflow/LangGraph runtime
- old tracker/import flows
- old provider paths and provider names: `local_db`, `gemini_cli`,
  `cuhksz_live`
- old demo/evaluation scripts
- old docs centered on deleted runtime paths

## Supporting docs

- [docs/V4_STATE_MACHINE.md](V4_STATE_MACHINE.md)
- [docs/V4_ERROR_CONTRACT.md](V4_ERROR_CONTRACT.md)
- [docs/V4_FRONTEND_ROUTE_GUARDS.md](V4_FRONTEND_ROUTE_GUARDS.md)
- [docs/CONFIRMED_PROFILE_PERSISTENCE.md](CONFIRMED_PROFILE_PERSISTENCE.md)
- [docs/LLM_ASSISTED_PROFILE_ENRICHMENT.md](LLM_ASSISTED_PROFILE_ENRICHMENT.md)
- [docs/LLM_PROMPT_AND_QUALITY_CONTROL.md](LLM_PROMPT_AND_QUALITY_CONTROL.md)
- [docs/PROFILE_FLOW_DECOUPLING.md](PROFILE_FLOW_DECOUPLING.md)
- [docs/PROFILE_REVIEW_QUALITY_EVALUATION.md](PROFILE_REVIEW_QUALITY_EVALUATION.md)
- [docs/SEARCH_READY_PROFILE_LAYER.md](SEARCH_READY_PROFILE_LAYER.md)
- [docs/SECTION_BASED_RESUME_PARSER.md](SECTION_BASED_RESUME_PARSER.md)
- [docs/GIT_WORKFLOW.md](GIT_WORKFLOW.md)
