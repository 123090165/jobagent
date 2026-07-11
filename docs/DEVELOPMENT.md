# Development Guide

## Maintainability Standard

Read the relevant call path, tests, contracts, and nearby conventions before
editing. Prefer the smallest coherent change that completes behavior end to end.

Use existing project boundaries:

- routes translate HTTP and inject identity;
- application use cases coordinate work and lifecycle;
- services own domain rules, provider access, parsing, and quality checks;
- repositories own persistence;
- schemas define validated contracts;
- frontend API modules and stores separate transport from pages.

Add an abstraction when it removes real duplication, isolates volatility, or
creates a clear ownership boundary. Do not add an abstraction only to shorten a
file or prepare for an imagined feature.

## Refactoring Policy

Use progressive refactoring:

- do not rewrite a working subsystem without a behavior-preserving path;
- do not postpone all cleanup until the product is feature-complete;
- refactor touched code when it lowers immediate change risk;
- use a dedicated refactor when several stages, contracts, or persistence
  boundaries move together.

For job_search_usecases.py, stop adding stage-specific policy. The next major
search or Job Brief feature should first extract the stages it needs to change.
Keep a thin application orchestrator and preserve tests, trace order, API
responses, and persisted data throughout the move.

Avoid hard file-length rules. Warning signs are mixed responsibilities,
duplicated policy, hidden side effects, difficult isolated testing, and changes
that repeatedly touch unrelated sections.

## Code Changes

- Preserve user changes in a dirty worktree.
- Keep unrelated formatting and cleanup out of feature diffs.
- Use deterministic parsers and validators for structured data.
- Keep LLM and provider implementations behind shared interfaces.
- Bound concurrency, retries, payload size, and external calls.
- Define partial-failure and fallback behavior.
- Make data ownership and state transitions explicit.
- Add comments only for non-obvious constraints or decisions.

The reusable project skill at skills/maintainable-coding contains the same
coding guidance for Codex-driven implementation and review.

## Testing

Scale checks with the change:

- focused unit tests for deterministic domain behavior;
- repository and API tests for persistence, ownership, and error contracts;
- integration tests for cross-stage workflows;
- frontend type/build checks for Vue changes;
- browser-helper tests plus manual browser verification for extension behavior;
- explicit live smoke tests only when validating external providers.

Default tests must not require network access, a hosted LLM, browser login, or a
real API key.

Current CI runs pytest only. Improve it before private beta:

1. run the Vue type check and production build;
2. validate the browser extension manifest and core message flows;
3. add dependency and secret scanning;
4. add a small end-to-end happy path;
5. retain focused test jobs so failures remain diagnosable.

## Verification Commands

~~~powershell
.venv\Scripts\python.exe -m pytest
cd web
npm run build
~~~

Run focused tests first while iterating. Run broader checks before committing a
cross-layer or shared-contract change. Report checks that could not run.

## Git

- Use a focused branch and commit message.
- Inspect status before editing and before committing.
- Stage only files belonging to the change.
- Do not commit local environment files, databases, generated reports, or
  credentials.
- Keep behavior changes, migrations, tests, and canonical documentation
  consistent in the same commit or tightly ordered commits.

## Documentation

docs/INDEX.md is the canonical entry point. Update current documents instead of
adding milestone notes. Git history replaces deleted-file logs and completed
implementation plans.

When code and docs disagree, verify behavior from code and tests, then update
the canonical document. Do not preserve stale text only because it records an
old decision.

## Review Checklist

- Does the behavior satisfy the user workflow, including failure and recovery?
- Is authorization enforced on the backend?
- Are external inputs and model output validated?
- Can the changed logic be tested without network or model calls?
- Does background work have bounded resource use?
- Are API and persisted-data compatibility intentional?
- Are logs and traces concise and free of secrets or sensitive full payloads?
- Did the change increase a mixed-responsibility module that should instead be
  split at a stable boundary?
