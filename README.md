# JobAgent

JobAgent is a local-first FastAPI and Vue application for turning resume
evidence into a confirmed candidate profile, provider-backed job search results,
and a user-owned saved-job library.

## Product Flow

~~~text
Register or login
-> Resume intake
-> Resume review
-> Profile draft
-> Confirmed resume profile
-> Search preview
-> Provider search and analysis
-> Search results
-> Saved jobs
~~~

Current product capabilities include:

- username/password authentication and user-owned resources;
- pasted text and .txt/.md/.pdf/.docx resume intake;
- deterministic resume parsing with optional LLM enrichment;
- editable and reusable resume profile library;
- deterministic or LLM-assisted search analysis;
- CUHKSZ Career, RemoteOK, LinkedIn discovery, Serper, mock, and multi-source
  provider adapters;
- browser-assisted BOSS search and current-page capture;
- persisted search traces, structured JD snapshots, and saved analysis.

Job Brief, resume tailoring, durable distributed workers, and a complete
application-outcome loop remain planned work.

## Stack

- backend: FastAPI, Pydantic, Python sqlite3;
- frontend: Vue 3, TypeScript, Vite, Pinia, Axios, Naive UI;
- local browser integration: Chrome/Edge Manifest V3 extension;
- LLM boundary: shared OpenAI-compatible JSON interface, with DeepSeek as the
  current hosted default;
- tests: pytest, network-free by default.

## Quick Start

Create the Python environment and install dependencies:

~~~powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
~~~

Copy configuration from .env.example into an ignored local env file and add
only the provider credentials you intend to use.

Start FastAPI:

~~~powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
~~~

Open the API documentation at http://127.0.0.1:8000/docs.

Start the Vue application:

~~~powershell
cd web
npm install
npm run dev
~~~

Run checks:

~~~powershell
.venv\Scripts\python.exe -m pytest
cd web
npm run build
~~~

## Browser Helper

Load browser-helper/ as an unpacked Chrome or Edge extension. It supports:

- helper and BOSS login-state checks;
- user-triggered BOSS search from Search Preview;
- BOSS candidates combined with backend-native providers;
- user-triggered current-page JD capture from the Side Panel.

BOSS cookies stay inside the local extension and are not sent to FastAPI. See
[docs/BROWSER_HELPER.md](docs/BROWSER_HELPER.md) for setup, permissions, and
known authentication limitations.

## Main Directories

- app/: FastAPI runtime, use cases, services, repositories, and schemas;
- web/: Vue user interface;
- browser-helper/: local browser-assisted provider bridge;
- experiments/: explicit provider and quality evaluation commands;
- tests/: automated regression coverage;
- docs/: current product and engineering guidance;
- skills/: reusable project skills for Codex-assisted development.

## Important Boundaries

- The frontend calls /api/v1 and never imports backend modules.
- Provider and LLM credentials stay server-side.
- Tests do not call live providers or hosted LLMs by default.
- No automatic application, CAPTCHA handling, or anti-bot bypass is supported.
- Missing authentication currently falls back to local-user for compatibility;
  do not expose the backend publicly until production auth mode is enforced.
- SQLite and in-process BackgroundTasks are local-MVP choices, not the public
  multi-user production target.

## Documentation

Start with [docs/INDEX.md](docs/INDEX.md). The roadmap, architecture, API,
security, search, browser-helper, and development guides there are canonical.
