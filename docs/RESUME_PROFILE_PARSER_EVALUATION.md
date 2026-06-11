# Resume Profile Parser Evaluation

## Why this exists

ResumeProfile is the upstream user model. Bad profile extraction contaminates job search, JD matching, resume rewrite, and interview challenge generation.

This baseline evaluates resume profile parsing as an independent product capability before downstream matching and optimization workflows consume the profile.

## Current parser architecture

```text
resume_text
-> ResumeParseAgent
-> mock_resume_parse
-> ResumeProfile
```

The product-facing review path is:

```text
resume_text
-> /resume/profile-review
-> parsed_profile
-> quality_warnings
-> missing_info_questions
-> editable_sections
-> confidence_label
```

The evaluation service calls `build_resume_profile_review()` directly, so it uses the same profile review contract as the API without requiring FastAPI, Ollama, or network access.

## Evaluation Cases

- AI Agent / Backend
- Embedded / STM32
- ML / Research
- Weak resume
- Rich resume

## Metrics

- skill hits
- project count
- work experience count
- education keyword match
- highlight keyword match
- warnings
- confidence label
- overall evaluation label

The overall evaluation label is separate from `profile_review.confidence_label`:

```text
failed_checks == 0 -> strong
failed_checks <= 2 -> medium
failed_checks <= 4 -> limited
else -> weak
```

## Known Limitations

- skill extraction depends on `KNOWN_SKILLS`
- English work experience may be under-detected
- embedded vocabulary coverage is weak
- project names are often generic
- education fields are not deeply parsed
- highlights are keyword-based

## How to Run

```bash
.venv\Scripts\python.exe scripts\run_resume_profile_parser_evaluation.py
```

This writes:

```text
docs/demo_outputs/resume_profile_parser_eval/summary.json
docs/demo_outputs/resume_profile_parser_eval/summary.md
```

## Next Step

v3.3 Section-based Resume Parser
