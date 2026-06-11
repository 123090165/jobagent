# Section-based Resume Parser

## Problem

The previous parser scanned the whole resume with simple keywords, which under-detected English experience, embedded skills, structured education, project names, and measurable highlights.

## Design

```text
resume_text
-> section detection
-> section-specific extraction
-> fallback to old heuristic
-> ResumeProfile
```

The parser remains deterministic and local. It does not call an LLM and it preserves `raw_text` as evidence for parsed education, work, and project items.

## Supported Sections

- skills
- education
- experience
- projects
- certificates / awards

Both English and Chinese headings are supported, including colon forms such as `Technical Skills: Python, FastAPI` and `项目经历：STM32 智能小车控制系统`.

## Improvements

- skill extraction from Skills section
- embedded vocabulary coverage
- English internship/research experience detection
- project title extraction
- education school/degree/major extraction
- metric/highlight extraction

## Guardrails

- no LLM
- no invented entities
- preserve `raw_text` as evidence
- fallback when structure is unclear
- keep weak, sparse resumes visibly incomplete

## Next Step

LLM-assisted profile enrichment can be added later, but only after deterministic parsing has a reliable baseline.
