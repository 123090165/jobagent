# Legacy Streamlit Frontend

`frontend/` is the legacy Streamlit demo/admin panel.

It is retained for internal testing and demos. The user-facing product frontend will live under `web/`.

Do not add new long-term product frontend features here unless a task explicitly asks for Streamlit work. New product flows should use the Vue 3 app in `web/` and communicate with the FastAPI backend through `/api/v1`.
