# Coaching Harness

Backend harness for the AI Startup Coach product.

This repository currently contains the backend scaffold, PostgreSQL schema models,
and Alembic migration for the database described in
`docs/coaching-harness-spec-en.md`.

## Configuration

Copy `.env.example` to `.env` and set:

- `DATABASE_URL`
- `LLM_BASE_URL` (for local 9Router: `http://localhost:20128/v1`)
- `LLM_API_KEY` (the API key created in 9Router; may be empty when key enforcement is disabled)
- `LLM_MODEL` (for example, `openai/gpt-4o-mini`)

Legacy `LLM_PROXY_*` and `OPENROUTER_*` variables are accepted as temporary
fallbacks, but the `LLM_*` variables are the primary configuration.
