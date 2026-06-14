# Search-Ready Profile Layer

## Why This Layer Exists

`ResumeProfile` is still a parser-oriented structure. It is useful for profile review,
but it is not yet the most ergonomic shape for search-ready candidate targeting.

`SearchReadyProfile` adds one deterministic layer on top of parsed resume evidence so
the system can describe a candidate in a more search-oriented product shape:

- short summary
- target directions
- core skills
- auxiliary skills
- search keywords
- preferences and follow-up notes

## Relationship to Existing Profile Types

- `ResumeProfile`
  - raw parser output
  - skills, projects, work experience, education, highlights
- `ConfirmedProfile`
  - persisted profile-review result after user confirmation
  - keeps suggestion decisions and missing-info answers
- `SearchReadyProfile`
  - deterministic derived layer for search-oriented downstream usage
  - does not replace parser output or confirmed profile storage

## Current Fields

- `summary`
  - 1-2 sentence search-oriented candidate summary
- `target_directions`
  - explicit or evidence-backed role directions
- `core_skills`
  - strongest matching capabilities for job search
- `auxiliary_skills`
  - tools, frameworks, languages, and supporting skills
- `search_keywords`
  - normalized role and skill terms useful for search
- `preferred_locations`
  - explicit location hints extracted from evidence
- `work_arrangements`
  - internship / remote / onsite / hybrid / full-time when clearly supported
- `company_preferences`
  - optional, evidence-backed company or sector preferences only
- `profile_notes`
  - concise follow-up notes for later review or editing
- `quality_warnings`
  - inherited parser/review warnings
- `missing_info_questions`
  - inherited follow-up questions when evidence is thin
- `source_profile_snapshot`
  - optional raw snapshot for debugging and evaluation

## Deterministic Builder Rules

The v3.9a builder is deterministic only.

It uses:

- parsed skills
- projects
- work experiences
- education
- highlights
- target roles
- quality warnings
- missing-info questions

It does not call:

- DeepSeek
- Ollama
- any external LLM

The builder uses category-specific heuristics for:

- AI agent / backend
- AI health / physiological signal processing
- ML / audio / ASR
- business / FA / finance
- embedded / STM32

Weak profiles remain constrained. The builder preserves warnings and questions and
does not invent role directions, company preferences, or inflated core skills.

## Why v3.9a Does Not Use LLM

This layer is intentionally deterministic so it can be:

- easy to test
- easy to review
- stable for downstream search integration
- safe to evaluate without extra model variance

## Next Step

v3.9b is expected to connect `SearchReadyProfile` into a frontend-editable profile
draft flow, but v3.9a stops at backend generation plus evaluation artifacts.
