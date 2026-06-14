# Profile Flow Decoupling

## Why v3.9c Exists

The earlier UI mixed profile creation with later-stage JD analysis and other
LLM-heavy tasks. v3.9c makes profile creation its own first-class flow.

The current product direction is:

```text
build candidate profile first
-> then continue to JD search / analysis
-> later resume optimization and project challenge
```

## What Changed

- Profile creation is now a step-by-step flow.
- Global LLM task checkboxes are replaced by provider selection.
- The default provider is local `ollama`.
- `deepseek` is an optional cloud provider.
- `mock` remains internal fallback only and is not shown as a primary user choice.

## Flow

```text
Step 1: Resume Input
Step 2: Parsed Resume Review
Step 3: Search-Ready Profile Draft
Step 4: Profile Saved
```

This keeps the user focused on establishing a clean, confirmed candidate
profile before moving to downstream workflows.

## Model Selection

Provider selection is treated as model context, not a set of task-specific
feature toggles.

Displayed metadata:

- provider
- model
- base_url
- configured
- reason

If the selected provider is unavailable, the flow keeps using deterministic
profile building and records the provider metadata for later reuse.

## Scope Boundary

This phase does not implement new JD search behavior.
It only provides the exit point to continue into JD search / analysis later.
