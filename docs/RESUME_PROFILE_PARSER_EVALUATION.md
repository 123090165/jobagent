# Resume Profile Parser Evaluation

## Why this exists

ResumeProfile is the upstream user model. Bad profile extraction contaminates job search, JD matching, resume rewrite, and interview challenge generation.

This baseline evaluates resume profile parsing as an independent product capability before downstream matching and optimization workflows consume the profile.

## Current parser architecture

```text
resume_text
-> ResumeParseAgent
-> mock_resume_parse
-> section detection
-> section-specific extraction
-> old heuristic fallback
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

v3.3 adds a section-based deterministic parser and uses this v3.2 evaluation
baseline to compare the upstream profile extraction layer. The enhanced parser
improves embedded skill coverage, English research/internship experience
detection, education extraction, project title extraction, and metric-based
highlights without introducing LLM risk.

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

- skill extraction still depends on a curated known-skill dictionary
- multi-line experience grouping remains lightweight
- embedded project evidence may still be thin without measurable outcomes
- project grouping is shallow for dense multi-project sections
- education parsing is heuristic and preserves raw text when uncertain
- highlights are keyword and metric based

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
