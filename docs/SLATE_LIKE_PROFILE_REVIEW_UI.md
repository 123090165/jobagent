# Slate-like Profile Review UI

## Goal

Turn parsed resume profile and LLM enrichment suggestions into editable
user-facing profile cards.

## Flow

```text
Resume input
-> parse
-> enrichment
-> section cards
-> accept/edit/reject suggestions
-> missing info answers
-> confirmed profile
```

## Design Principle

The UI does not let LLM overwrite the profile automatically. Users decide what
to accept, edit, or reject, and the deterministic parsed profile remains the
baseline evidence source.

## Current Scope

- Streamlit implementation
- section cards for skills, projects, work experience, education, certificates,
  and highlights
- profile draft state in the frontend
- suggestion accept/edit/reject decisions
- missing-info answers collected into draft notes
- existing confirm API reuse
- no auth
- no persistence
- no database changes

## Future Work

Persist confirmed profile and suggestion decisions.
