# JobAgent Documentation

This directory contains current product and engineering guidance. It is not a
history archive. Git preserves completed plans and deleted designs.

## Canonical Documents

- [CODE_FLOW_ZH.md](CODE_FLOW_ZH.md): 中文代码链路、运行边界，以及旧代码和
  旧说明的待清理标注。
- [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md): product status, priorities, and
  delivery sequence.
- [ARCHITECTURE.md](ARCHITECTURE.md): runtime boundaries, workflow state, and
  refactoring direction.
- [API_CONTRACT_V1.md](API_CONTRACT_V1.md): current public API groups and error
  behavior.
- [DATA_SECURITY.md](DATA_SECURITY.md): persistence, authentication, privacy,
  migration, and deployment boundaries.
- [SEARCH_PROVIDER.md](SEARCH_PROVIDER.md): providers, ranking, LLM quality
  controls, tracing, and future workflow evolution.
- [BROWSER_HELPER.md](BROWSER_HELPER.md): browser extension behavior and safety
  boundary.
- [DEVELOPMENT.md](DEVELOPMENT.md): coding, testing, documentation, and
  refactoring practices.
- [SEARCH_HISTORY_RECOVERY.md](SEARCH_HISTORY_RECOVERY.md): user-visible run
  history and the current recovery boundary.
- [SEARCH_MISSION.md](SEARCH_MISSION.md): intent collection, agent
  interpretation, conflict detection, confirmation, and search integration.
- [JOB_BRIEF.md](JOB_BRIEF.md): versioned saved-job decision and action briefs.
- [STREAMLINED_PRODUCT_FLOW.md](STREAMLINED_PRODUCT_FLOW.md): three-stage user
  flow and the Search Analysis versus Job Brief responsibility boundary.
- [INTERVIEW_PREPARATION.md](INTERVIEW_PREPARATION.md): evidence gaps, MCP
  learning resources, user questions, and external-model exchange.
- [MODULAR_RAG_MCP.md](MODULAR_RAG_MCP.md): independent Modular RAG service,
  MCP client contract, typed tool adapters, and live verification.
- [LOCAL_RAG_END_TO_END_CHECKLIST.md](LOCAL_RAG_END_TO_END_CHECKLIST.md):
  live-service automation and the minimal manual acceptance checklist for
  JobAgent, the sync worker, and Modular RAG.

## Documentation Rules

- Describe current behavior in present tense.
- Put future work only in PRODUCT_ROADMAP.md unless it is a subsystem constraint.
- Update contracts when an API, environment variable, state transition, or
  persistence rule changes.
- Avoid milestone diaries, deleted-file lists, and duplicated file inventories.
- Prefer links to source directories over lists of every source file.

## Current Product Flow

> 标注：下列是内部资源链路，不等同于前端展示的三个阶段；当前界面将 Mission
> 收集与 Search Preview 合并为统一的 Search Setup。

~~~text
User login
-> Resume intake
-> Resume review
-> Profile draft
-> Confirmed resume profile
-> Search preview
-> Provider search and analysis
-> Search results
-> Saved job library
-> Job Brief
~~~

Resume tailoring and a complete application workflow remain planned product flows.
