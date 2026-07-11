# JobAgent Documentation

This directory contains current product and engineering guidance. It is not a
history archive. Git preserves completed plans and deleted designs.

## Canonical Documents

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
- [JOB_SEARCH_USECASE_REFACTOR_PLAN.md](JOB_SEARCH_USECASE_REFACTOR_PLAN.md):
  phased behavior-preserving split of the current search use-case module.

## Documentation Rules

- Describe current behavior in present tense.
- Put future work only in PRODUCT_ROADMAP.md unless it is a subsystem constraint.
- Update contracts when an API, environment variable, state transition, or
  persistence rule changes.
- Avoid milestone diaries, deleted-file lists, and duplicated file inventories.
- Prefer links to source directories over lists of every source file.

## Current Product Flow

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
~~~

Job Brief, resume tailoring, and a complete application workflow are planned,
not implemented product flows.
