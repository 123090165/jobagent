# JobAgent Repository Guide

These instructions apply to the whole repository.

## Working Rules

- Do not use subagents unless the user explicitly asks for delegation or
  parallel agent work in the current request.
- Preserve unrelated local changes and inspect `git status` before editing.
- Keep changes small, direct, and compatible with current API and persistence
  contracts.
- Keep provider, MCP, and LLM calls bounded and behind existing interfaces.
- Preserve authorization, local-first security, partial-failure, and recovery
  behavior.
- Prefer deterministic, network-free checks during development.
- Run focused tests first, broader checks for shared contracts, the Vue build
  for frontend changes, and `git diff --check` before handoff.

## Project Boundaries

- `app/api/v1`: HTTP transport and identity dependencies.
- `app/application`: use-case orchestration and ownership checks.
- `app/services`: domain rules and external-service adapters.
- `app/repositories`: persistence.
- `app/schemas`: validated contracts.
- `web`: Vue frontend.

Canonical product and engineering documentation starts at `docs/INDEX.md`.
