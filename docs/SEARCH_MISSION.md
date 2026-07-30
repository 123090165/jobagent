# Search Mission

> 当前实现标注：Search Mission 仍是有效的后端资源，但独立前端页面已合并到
> Search Preview。旧 `/search-mission` URL 仅作为重定向兼容入口。

## Purpose

A confirmed resume describes demonstrated experience. A Search Mission describes
what the user wants now. JobAgent keeps these concepts separate so search and
ranking can explain both capability fit and intent fit.

The workflow is:

~~~text
Confirmed profile
-> collect intent
-> structure intent
-> detect conflicts and assumptions
-> ask at most three high-impact questions
-> user edits and confirms the mission
-> preview and execute search
~~~

Search Mission is a sub-resource of a profile session. It does not add another
top-level `ProfileSessionStep`; existing sessions remain compatible.

## Data Model

Each profile session owns at most one current mission. The persisted record
contains:

- user input: target and excluded roles, industries, locations, work
  arrangements, employment types, must-have and nice-to-have conditions,
  ranking priorities, exploration level, and a free-text statement;
- structured intent: normalized values plus adjacent roles, hard constraints,
  soft preferences, conflicts, assumptions, and clarification questions;
- lifecycle: `draft`, `review`, or `confirmed`;
- analysis metadata: `deterministic`, `llm`, or `fallback`, provider, fallback
  reason, timestamps, and a monotonically increasing revision.

The unique ownership key is `(user_id, session_id)`. The backend derives user,
session, and confirmed-profile ownership; clients cannot assign them.

## Agent Boundary

The mission interpreter is a focused skill behind JobAgent's shared
`JSONChatLLM` interface. It receives the confirmed profile and user input and
must:

1. distinguish hard constraints from preferences;
2. normalize role and location language without inventing preferences;
3. detect conflicts between requested direction and resume evidence;
4. state assumptions explicitly;
5. return no more than three questions whose answers materially affect search.

Deterministic interpretation is always available. An LLM failure returns a
deterministic mission with `analysis_mode=fallback`; it never blocks editing or
confirmation. The first version uses one JSON request and does not require
LangGraph. A checkpointed clarification graph is deferred until multi-turn
branching is a demonstrated requirement.

## Confirmation Rules

- The user can edit the source intent and rerun interpretation before
  confirmation.
- Confirmation requires at least one target role.
- Questions are advisory in the first version; confirmation means the user has
  accepted or resolved the remaining ambiguity.
- Re-editing a confirmed mission returns it to `draft`; a new confirmation
  increments the revision without deleting prior search runs.

## Search Integration

When a confirmed mission exists, preview and run creation use its target roles,
locations, and positive search signals unless the API request explicitly
overrides a field. Each run snapshots the mission id, revision, hard constraints,
excluded roles, and ranking priorities. Candidate filtering consumes the
snapshot in both LLM and deterministic modes. A deterministic post-validation
penalty enforces excluded signals even when an LLM scorecard omits them.

## Non-Goals

- autonomous changes to user intent based on feedback;
- unlimited clarification loops;
- automatic rejection of a mission because resume evidence is weak;
- framework-specific state in API or repository contracts;
- replacing the confirmed resume profile.

## Acceptance Checks

- Mission ownership is isolated by authenticated user and profile session.
- Deterministic interpretation and conflict detection work without an LLM.
- LLM output is validated and falls back safely.
- A mission can be edited, interpreted, confirmed, reopened, and revised.
- Search Preview receives confirmed mission defaults.
- Existing sessions without a mission continue to use confirmed-profile defaults.
