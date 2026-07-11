# JobAgent Web

web/ is the Vue 3 product frontend. It uses TypeScript, Vite, Vue Router, Pinia,
Axios, and Naive UI, and communicates with FastAPI only through /api/v1.

## Boundaries

- Put typed HTTP clients in src/api/.
- Put shared workflow and user state in src/stores/.
- Keep product views in src/pages/.
- Do not import Python modules or backend implementation details.
- Never store provider or LLM API keys in the frontend.

## Current Views

- login and registration;
- resume intake and profile review;
- editable profile draft and confirmed profile;
- resume profile library;
- search preview and browser-helper controls;
- live search status, traces, results, and save actions;
- saved job library.

The router requires login for product routes and checks backend ProfileSession
state before entering workflow pages. Backend authorization remains the real
security boundary.

## Development

~~~bash
npm install
npm run dev
npm run build
~~~

Vite proxies /api to http://localhost:8000 by default. Set VITE_API_BASE_URL
when the API is hosted elsewhere.

See ../docs/INDEX.md for current product, API, architecture, and development
guidance.
