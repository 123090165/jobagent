# Search Subagent Operating Model

## Purpose

JobAgent uses project-scoped Codex custom agents to make Search Retrieval Quality V2 work repeatable. Each agent has a narrow role, stable developer instructions, an appropriate model and permission boundary, and a common handoff contract.

The configuration files are stored in `.codex/agents/`. They are reusable by future Codex sessions opened in this trusted repository.

## Agent Roster

| Agent | Mode | Model | Write scope | Best used for |
| --- | --- | --- | --- | --- |
| `search_architect` | Read-only | `gpt-5.6-sol`, medium | None | Cross-stage contracts, migration design, architecture decisions |
| `search_retrieval_engineer` | Workspace write | `gpt-5.6-sol`, medium | Planner, preview, providers, recall and related tests | Typed query plan, translation, quotas, scheduler, clustering |
| `search_ranking_engineer` | Workspace write | `gpt-5.6-sol`, medium | Filter, analysis, scoring, assembly and related tests | Hard constraints, evidence extraction, final ranking |
| `search_quality_evaluator` | Workspace write | `gpt-5.6-luna`, medium | Experiments, fixtures, evaluation tests/docs by default | Baselines, metrics, calibration, regression analysis |
| `search_quality_reviewer` | Read-only | `gpt-5.6-sol`, medium | None | Independent integrated review and missing-test detection |

The evaluator uses Luna because its normal work is clear, repeatable, and structured across many fixtures. Architecture, complex implementation, and adversarial review use Sol because they handle ambiguous contracts and cross-stage correctness. All project agents use medium reasoning effort.

## Why These Roles

The Search V2 plan has two main write domains:

~~~text
Intent/query/provider/recall
  -> owned by search_retrieval_engineer

Constraint/pre-rank/JD evidence/final score
  -> owned by search_ranking_engineer
~~~

Architecture and quality evaluation cut across both domains but should not silently rewrite production behavior. The independent reviewer remains read-only so review cannot turn into untracked self-approval.

No separate “frontend search agent” is defined yet. Current frontend work is mostly trace and contract consumption, and does not justify a permanent specialist. Add one only if Search V2 creates a sustained frontend-specific workflow with its own tests and decisions.

## Recommended Dispatch Patterns

### Designing a phase

Ask the primary agent to use `search_architect` for the relevant phase, wait for its evidence-backed handoff, and then turn the design into bounded implementation tasks.

Example request:

~~~text
Use the search_architect agent to inspect Phase 3 of the Search Retrieval Quality V2 plan. Return the exact schema boundary, migration sequence, affected tests, and one bounded task for the retrieval engineer. Do not edit files.
~~~

### Implementing an isolated retrieval slice

~~~text
Delegate Phase 1 query typing to search_retrieval_engineer. Limit the task to planner schemas, deterministic selector shadow output, preview trace details, and focused tests. Preserve current provider execution behavior.
~~~

### Parallel work

The primary agent may run the evaluator alongside one implementation agent when they do not edit overlapping files. For example, the evaluator can prepare constraint fixtures while the retrieval engineer implements shadow query selection.

Do not run retrieval and ranking writers in parallel until shared schemas are fixed. Never run two instances that write the same modules.

### Integrated review

~~~text
After implementation and tests, use search_quality_reviewer to review the integrated diff against the delegated phase. Wait for it and report blocker/high findings before declaring completion.
~~~

## Task Packet Template

~~~text
Objective:
Relevant V2 phase:
Verified current behavior:
In-scope files/contracts:
Out of scope:
Compatibility requirements:
Required tests/metrics:
Edits allowed: yes/no
Expected handoff:
~~~

A task packet should fit one independently testable change. If it includes planner, Provider orchestration, hard filtering, JD scoring, persistence, and frontend changes together, split it first.

## How the System Compounds

Custom agent prompts stay stable, but they are not long-term memory. Compounding comes from turning each verified result into durable project evidence:

1. Tests preserve discovered edge cases.
2. Evaluation fixtures preserve relevance and constraint examples.
3. Baseline scripts make later quality changes comparable.
4. Canonical docs preserve decisions and rejected alternatives.
5. Provider adapter tests preserve source-specific quirks.
6. Trace contracts make production behavior observable.

Agents should not maintain private diaries or append raw conversation summaries. Future agents benefit more from a failing regression test, a typed contract, or a reproducible metric than from narrative memory.

## Governance

- The primary agent remains accountable for the combined result.
- A subagent recommendation is not accepted until its evidence or diff is inspected.
- Read-only agents never make repository changes.
- Write agents stay within the task packet and their normal ownership boundary.
- Model or reasoning settings may be adjusted later using measured quality, latency, and token usage; role responsibilities should remain stable unless the architecture changes.
- Review agent findings are resolved or explicitly accepted as residual risk before a Search V2 milestone is complete.

## Installation and Availability

Codex loads project agents from `.codex/agents/` in a trusted repository. If an already-open client does not show the new agent types, reopen the repository or start a new Codex session so configuration is reloaded.

Custom agents consume separate model and tool work. Use them when independence, context isolation, or specialist review materially improves the outcome; avoid delegation for small edits.
