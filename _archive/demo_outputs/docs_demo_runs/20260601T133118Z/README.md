# Gemini Search Demo Run

- Timestamp: 20260601T133118Z
- Query: demo shenzhen ai agent developer jobs
- GeminiCLIProvider Enabled: True
- Tried URL Import: True
- URL Import Succeeded: False
- Used Fallback JD Draft: True
- /analyze/full Succeeded: True
- Used LLM: False
- Used LangGraph: False
- save_result: False
- Gemini CLI Command Overridden: True
- Raw Output Directory: demo_runs\20260601T133118Z

## Current Limitations
- This demo does not upload full resume_text to Gemini CLI.
- The script does not auto-save to SQLite unless --save-result is explicitly provided.
- Search results do not automatically trigger JD import or analysis outside this script.
- The published record is sanitized and does not include raw Gemini output or full JD text.

## Warnings
- JD URL import failed: JD URL must return text/html or text/plain content (jd_url_content_type_unsupported)

## Follow-up Suggestions
- Add a JobImportCandidate review step before any future storage or analysis automation.
- Keep URL import optional and user-confirmed for provider outputs with weak snippets.
- Consider richer sanitized step summaries if future demo reviews need more observability.
