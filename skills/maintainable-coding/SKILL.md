---
name: maintainable-coding
description: Implement and review code with maintainability-focused judgment. Use for feature work, bug fixes, refactoring, API or data-model changes, and code review when Codex should preserve existing architecture, keep changes scoped, avoid unnecessary abstractions, protect compatibility, and verify behavior without imposing rigid style rules.
---

# Maintainable Coding

Favor code that the next developer can understand and change safely. Treat these as judgment guidelines, not mechanical gates.

## Working Method

1. Read the relevant call path, tests, contracts, and nearby conventions before editing.
2. State assumptions when requirements or ownership boundaries are unclear.
3. Choose the smallest coherent change that completes the behavior end to end.
4. Keep domain rules out of transport, UI, and persistence adapters when an existing boundary supports that separation.
5. Verify the changed behavior at the narrowest useful level, then broaden checks according to risk.
6. Review the final diff for accidental churn, stale documentation, compatibility breaks, and hidden failure paths.

## Design Judgment

- Prefer existing project patterns and shared interfaces over introducing a parallel architecture.
- Add an abstraction when it removes meaningful duplication, isolates volatility, or establishes a real ownership boundary. Do not add one only to shorten a file.
- Keep orchestration readable: it should coordinate steps, while parsing, provider access, validation, scoring, and persistence live behind focused functions or services.
- Split a growing module incrementally at stable seams. Avoid both a speculative rewrite and postponing all cleanup until the end.
- Preserve public API and persisted-data compatibility unless the task explicitly changes them. Make migrations and invalidation behavior explicit.
- Use deterministic behavior for validation, normalization, deduplication, and safety rules. Keep model output advisory and schema-validated.
- Avoid global state and process-local assumptions when work must survive restarts or support multiple users.

## Change Scope

- Do not mix unrelated cleanup into feature work.
- Refactor code touched by the change when doing so lowers immediate implementation risk.
- Schedule a separate refactor when a boundary affects several modules, persistence contracts, or runtime orchestration.
- Preserve user changes in a dirty worktree and call out conflicts instead of overwriting them.
- Update canonical documentation when behavior, API contracts, configuration, or architectural decisions change.

## Reliability And Security

- Define failure behavior for external services, background work, and partial results.
- Bound concurrency, retries, payload size, and resource use where requests can multiply.
- Enforce authorization at backend ownership boundaries; frontend guards are usability features, not security controls.
- Treat uploaded files, scraped pages, provider text, model output, URLs, and stored JSON as untrusted input.
- Keep secrets server-side and avoid logging credentials, tokens, resumes, or full sensitive payloads.

## Verification

- Add or update focused tests for changed behavior and important failure cases.
- Run type/build checks for touched frontend code and targeted tests for touched backend code.
- Use integration or end-to-end checks for cross-layer flows instead of relying only on source-text assertions.
- If a check cannot run, report that explicitly.
- Do not claim performance, concurrency, or recovery properties without measurements or a test that exercises them.
