# JobAgent

> This repository is currently being refactored toward the v4 ProfileSession flow. Some older tracker/demo documentation may be legacy and is tracked in [docs/CLEANUP_AUDIT.md](docs/CLEANUP_AUDIT.md).

## What Is JobAgent?

JobAgent 是一个面向求职准备场景的本地工作台，用来把岗位来源、候选岗位、投递 tracker、单岗位深度分析和 evidence-based report 串成可复盘流程。

它不是一个单纯的 chatbot，也不是一个通用爬虫项目。当前重点是把求职闭环做扎实、做可测试、做可解释。

## Core Loop

```text
Job Source
  -> SearchResultItem
  -> JobImportCandidate
  -> ApplicationRecord
  -> Application Deep Analysis
  -> Evidence-based Final Report
```

## Key Features

- Search providers: `mock` / `local_db` / `gemini_cli` / `cuhksz_live`
- Candidate-to-tracker workflow
- Application deep analysis
- Requirement-level evidence matching
- Evidence-based resume rewrite suggestions
- Grounded project challenge questions
- JD-Resume Evidence Chain report
- Analysis Quality Gate
- Optional LLM enhancement with fallback
- SQLite persistence and workflow trace

## Quick Start

Create and set up the virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run tests:

```powershell
.venv\Scripts\python.exe -m pytest
```

Start FastAPI:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Optional: start the Streamlit demo:

```powershell
.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Stable demo mode recommendation:

- prefer `mock` or `local_db`
- treat `cuhksz_live` as optional live demo only
- treat LLM as optional enhancement, not main-path dependency

## Demo Path

Recommended 3-5 minute walkthrough:

1. Run the backend and open `/docs`
2. Search jobs through `mock` or `local_db`
3. Review `SearchResultItem` metadata and warnings
4. Create or review `JobImportCandidate`
5. Import the candidate into `ApplicationRecord`
6. Run `POST /applications/{application_id}/analyze`
7. Open the final report and explain the evidence chain plus analysis quality

More detail: [Demo Guide](docs/DEMO_GUIDE.md)

## Project Architecture

Main directories:

- `app/api`: FastAPI route layer and API boundaries
- `app/agents`: resume, JD, match, optimization, challenge, and report agents
- `app/services`: business orchestration and provider-facing services
- `app/workflows`: explicit workflow orchestration and trace handling
- `app/schemas`: shared Pydantic contracts
- `app/storage`: SQLite connection and repositories
- `tests`: unit and integration coverage
- `docs`: architecture, demo, workflow, and boundary docs

Architecture docs:

- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)
- [Workflow Architecture](docs/WORKFLOW_ARCHITECTURE.md)

## Documentation

Core docs:

- [Demo Guide](docs/DEMO_GUIDE.md)
- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)
- [Workflow Architecture](docs/WORKFLOW_ARCHITECTURE.md)
- [Live Job Provider](docs/LIVE_JOB_PROVIDER.md)
- [Application Tracker](docs/APPLICATION_TRACKER.md)
- [Job Import Candidate](docs/JOB_IMPORT_CANDIDATE.md)
- [Search Provider](docs/SEARCH_PROVIDER.md)

## Current Boundaries

Current non-goals:

- AI Interview session
- RAG question bank
- multi-site generic crawler
- auto apply
- email/calendar reminders
- multi-user auth
- PDF/DOCX export

Also intentionally out of scope for the current phase:

- login flows
- captcha handling
- browser automation
- unsupported resume fabrication

## Development Notes

- deterministic core first
- mock-first and testable
- LLM optional / fallback
- schema-first
- no unsupported resume fabrication

## Notes For Reviewers

What this project should be judged on:

- whether the core loop is clear and runnable
- whether the analysis result is evidence-based instead of score-only
- whether tracker and analysis boundaries are explicit
- whether the system remains useful without real-time LLM dependencies
- whether the behavior is testable and locally reproducible
