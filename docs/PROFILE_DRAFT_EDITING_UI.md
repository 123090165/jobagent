# Profile Draft Editing UI

## Goal

v3.9b adds an editable `ProfileDraft` layer on top of `SearchReadyProfile`.
The draft gives the user one place to review and adjust a search-ready profile
before it is confirmed for later search and matching.

## Why ProfileDraft Exists

`SearchReadyProfile` is deterministic system output.
`ProfileDraft` adds the user-editable review state that sits between:

```text
parsed profile -> search-ready profile -> user edits -> confirmed payload
```

This keeps system-generated structure separate from user-confirmed intent.

## Relationship

- `ResumeProfile`:
  parser-oriented factual extraction.
- `SearchReadyProfile`:
  deterministic search-ready candidate view.
- `ProfileDraft`:
  editable review wrapper around `SearchReadyProfile`.

## Draft Fields

`ProfileDraft` stores:

- `draft_id`
- `status`
- `search_ready_profile`
- `user_answers`
- `user_edit_snapshot`
- `source_profile_snapshot`
- `created_at`
- `updated_at`

## Editing Flow

The current UI flow is:

```text
resume text
-> parser/profile review API
-> SearchReadyProfile builder
-> editable ProfileDraft
-> user edits summary / chips / preferences / missing-info answers
-> confirm
-> confirmed profile payload ready
```

Editable draft sections:

- summary
- target directions
- core skills
- auxiliary skills
- search keywords
- preferred locations
- work arrangements
- company preferences
- profile notes

Read-only sections:

- quality warnings
- parsed raw evidence snapshot

## Missing Info Questions

Missing-info questions remain visible in the draft.
User answers are saved into `user_answers` and also appended to
`profile_notes` for review context.

## Confirmed Payload

`confirm_profile_draft()` returns a payload with:

- `confirmed_search_ready_profile`
- `source_profile_snapshot`
- `user_edit_snapshot`
- `missing_info_answers`
- `confirmed_at`

## Persistence Scope

This phase prepares a confirmed payload for reuse and later persistence.
It does not add new job-search behavior or database schema changes.

## Out of Scope

v3.9b does not:

- run job search from this page
- call MatchAgent or downstream job-analysis agents
- auto-rewrite profile content with DeepSeek or Ollama
- add complex per-project/per-work structured editors
