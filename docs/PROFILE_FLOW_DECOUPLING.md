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
- The default provider is `deepseek`.
- Local `ollama` remains selectable through the provider abstraction.
- `mock` remains internal fallback only and is not shown as a primary user choice.

## Flow

```text
Step 1: Add Resume
Step 2: Parsed Resume Review
Step 3: Search-Ready Profile Draft
Step 4: Profile Saved
```

This keeps the user focused on establishing a clean, confirmed candidate
profile before moving to downstream workflows.

Step 1 is now the product entry point. The user can upload a `.txt` or `.md`
resume file or paste full resume text directly. Uploaded files are converted
into `resume_text` only; they do not bypass Profile Review or jump ahead in the
flow. PDF, DOCX, and OCR support remain out of scope for this phase.

The homepage no longer preloads a sample resume by default. The default entry
state is an empty resume box plus an explicit `Load sample resume` action for
demo use only. The sidebar is narrowed to model-provider selection so Profile
Setup stays the obvious first step before later search or analysis pages.

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
