# Coaching Harness

Backend harness for the AI Startup Coach product.

This repository currently contains the backend scaffold, PostgreSQL schema models,
and Alembic migration for the database described in
`docs/coaching-harness-spec-en.md`.

## Configuration

Copy `.env.example` to `.env` and set:

- `DATABASE_URL`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`

The OpenRouter model value is intentionally configurable because valid model
slugs can change.
