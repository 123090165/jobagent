# Confirmed Profile Persistence

## Problem

Slate-like profile review produces confirmed profiles and suggestion decisions,
but they were previously only kept in frontend session state.

## Design

A single SQLite table stores confirmed profile records. Suggestion decisions and
missing-info answers are stored as JSON snapshots rather than normalized
analytics tables.

```text
resume text
-> parser
-> profile review
-> LLM enrichment
-> Slate-like UI
-> confirmed profile persistence
-> profile-driven search and analysis
```

## Why One Table

This is an MVP without real user analytics needs. A single table keeps the
implementation simple while preserving enough data for future reuse.

## API

- `POST /profile/confirmed`
- `GET /profile/confirmed`
- `GET /profile/confirmed/{id}`

## Scope

- SQLite local persistence
- no auth
- no user accounts
- no vector DB
- no separate suggestion-decision table

## Future Work

Use saved confirmed profiles as job search and analysis context. Split
suggestion decisions into analytics tables only when real user feedback data
exists.
