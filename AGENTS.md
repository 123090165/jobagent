# JobAgent Agent Collaboration Guide

## Scope

These instructions apply to the whole repository. They complement `docs/DEVELOPMENT.md`; they do not replace product, security, API, or architecture contracts.

## Project Search Agents

Project-scoped custom agents live in `.codex/agents/`:

- `search_architect`: read-only cross-stage design and migration boundaries.
- `search_retrieval_engineer`: typed queries, provider translation, quotas, scheduling, recall metrics, and clustering.
- `search_ranking_engineer`: hard constraints, pre-rank, JD evidence, final scoring, and result diversity.
- `search_quality_evaluator`: offline fixtures, calibration, metrics, budgets, and outcome evaluation.
- `search_quality_reviewer`: read-only adversarial review of Search V2 changes.

Use these agents for Search Retrieval Quality V2 work when the task is independently bounded and substantial. Do not spawn agents for trivial edits, simple questions, or work whose coordination cost exceeds its benefit.

## Delegation Protocol

The primary agent owns requirements, decomposition, shared-contract decisions, merge order, final verification, and the user-facing answer.

For a cross-stage search change, use this sequence:

1. Ask `search_architect` to verify boundaries when the contract or migration path is ambiguous.
2. Assign implementation to exactly one owning writer for each overlapping module set.
3. Run `search_quality_evaluator` independently for baseline or regression evidence when quality behavior changes.
4. Ask `search_quality_reviewer` to review the integrated diff before completion.

Parallelize read-heavy architecture, evaluation design, exploration, and review preparation when useful. Do not let multiple write-capable agents edit the same files concurrently. Retrieval and ranking implementation may run in parallel only when their schema/interface contract is already fixed and their file ownership does not overlap.

Keep agent nesting at one level. Subagents must not delegate again unless the user explicitly requests recursive delegation and the primary agent defines a bounded reason.

## Required Task Packet

Every delegated task must include:

- one concrete objective;
- in-scope and out-of-scope files or contracts;
- the relevant phase in `docs/SEARCH_RETRIEVAL_QUALITY_V2_PLAN.md`;
- behavior and compatibility constraints;
- required tests or metrics;
- whether edits are allowed;
- the expected handoff format.

Do not ask an agent to “implement Search V2” as one task. Delegate one independently verifiable slice.

## Durable Knowledge

Subagent threads are working context, not project memory. Durable learning must land in the repository through the appropriate artifact:

- product and delivery decisions: canonical docs under `docs/`;
- architecture tradeoffs: the relevant architecture or subsystem plan;
- executable behavior: focused tests and typed contracts;
- evaluation knowledge: reusable fixtures, metric definitions, and baseline scripts under `experiments/` or `tests/`;
- provider quirks: provider adapter tests and `docs/SEARCH_PROVIDER.md`;
- temporary logs and raw live reports: keep untracked unless explicitly requested.

Do not create diary-style agent memory files. Consolidate verified learning into existing canonical artifacts so future agents inherit evidence rather than anecdotes.

## Shared Handoff Standard

Every subagent returns:

1. Outcome.
2. Evidence or files changed.
3. Verification performed and exact results.
4. Contract, fallback, and compatibility impact.
5. Remaining risks, assumptions, or blockers.
6. Recommended next bounded task or reviewer focus.

The primary agent must inspect the actual diff and test output before accepting a handoff.

## Repository Rules

- Preserve unrelated user changes and inspect git status before editing.
- Use deterministic, network-free tests by default.
- Keep provider and LLM calls bounded and behind existing interfaces.
- Preserve authorization, local-first security boundaries, partial failure, and recovery behavior.
- Do not add a workflow framework or Provider merely to simplify a delegated task.
- Keep API, persistence, trace, and frontend compatibility intentional and documented.
- Run focused tests first, broader tests for shared contracts, and `git diff --check` before handoff.
