# JobAgent Web

`web/` is the Vue 3 user-facing product frontend for JobAgent.

It uses Vite, TypeScript, Vue Router, Pinia, Axios, and Naive UI. It talks to the FastAPI backend through `/api/v1`.

## Boundary

- Do not import Python backend modules from `web/`.
- Do not import `app.services`, `app.schemas`, or any backend implementation details.
- Use typed API clients in `src/api/`.
- Use Pinia stores in `src/stores/` for client workflow state.

## Current Flow

The current v4 shell includes:

- Home page with Resume Intake
- StepProgress component
- Profile review cards
- Profile draft editing page
- Confirmed profile page
- ProfileSession API client
- ProfileSession Pinia store

The Resume Intake flow can:

- create a `ProfileSession`
- submit pasted resume text
- upload `.txt` and `.md` files
- navigate to `/profile/:sessionId/review`

The Resume Review flow can:

- call `/api/v1/profile-sessions/{session_id}/parse-resume`
- load `/api/v1/profile-sessions/{session_id}/parsed-review`
- render structured review cards for parsed resume understanding

The Profile Draft flow can:

- call `/api/v1/profile-sessions/{session_id}/profile-draft`
- load `/api/v1/profile-drafts/{draft_id}`
- patch `/api/v1/profile-drafts/{draft_id}`
- confirm through `/api/v1/profile-drafts/{draft_id}/confirm`

The Confirmed Profile flow can:

- load `/api/v1/confirmed-profiles/{confirmed_profile_id}`
- render the final search-ready profile
- show a Start Job Search placeholder for v4.5a

## Local Development

Install dependencies when network access is available:

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000` by default. Set `VITE_API_BASE_URL` if the backend is hosted elsewhere.
