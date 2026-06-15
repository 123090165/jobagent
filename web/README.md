# JobAgent Web

`web/` is the Vue 3 user-facing product frontend for JobAgent.

It uses Vite, TypeScript, Vue Router, Pinia, Axios, and Naive UI. It talks to the FastAPI backend through `/api/v1`.

## Boundary

- Do not import Python backend modules from `web/`.
- Do not import `app.services`, `app.schemas`, or any backend implementation details.
- Use typed API clients in `src/api/`.
- Use Pinia stores in `src/stores/` for client workflow state.

## Current Shell

The first shell includes:

- Home page
- StepProgress component
- Profile review, draft, and confirmed placeholder pages
- ProfileSession API client
- ProfileSession Pinia store

The current start button calls:

```ts
client.post("/api/v1/profile-sessions");
```

## Local Development

Install dependencies when network access is available:

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000` by default. Set `VITE_API_BASE_URL` if the backend is hosted elsewhere.
