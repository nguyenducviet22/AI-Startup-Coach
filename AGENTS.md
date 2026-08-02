# AI Startup Coach repository guide

## Project overview

This repository contains an AI-assisted startup coaching product. The backend is
a FastAPI application with async SQLAlchemy persistence, deterministic coaching
tools, document/report generation, and an OpenAI-compatible LLM client. The
frontend is a React and TypeScript single-page application built with Vite.

## Repository layout

- `app/`: FastAPI routes, domain models, services, tools, and LLM integration.
- `tests/`: backend unit, service, API, security, and evaluation tests.
- `evals/`: deterministic evaluation runner and fixtures.
- `app/db/migrations/`: Alembic database migrations.
- `frontend/`: React application, API clients, stores, features, and UI tests.
- `docs/`: specifications, implementation plans, deployment notes, and handoffs.

Read the nearest nested `AGENTS.md` before editing `app/` or `frontend/`.

## Setup and canonical checks

Backend setup and checks:

```text
python -m pip install -e ".[dev]"
python -m ruff check app tests evals
python -m pytest
python -m evals.run
```

Frontend setup and checks:

```text
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

Run the smallest relevant test first, then the full affected suite before
finishing. Changes spanning both applications require both sets of checks.

## Engineering conventions

- Keep HTTP concerns in API routes and business behavior in services/domain code.
- Preserve async boundaries for database and network operations.
- Validate external input at API/tool boundaries; do not trust LLM output.
- Keep deterministic startup-stage rules and evaluations independent of live LLM calls.
- Add or update tests for behavior changes and regressions.
- Never commit `.env`, credentials, generated artifacts, virtual environments, or build output.
- Do not edit existing Alembic migrations after they may have shipped; add a new migration.
- Do not silently change API response shapes used by `frontend/src/api/`.

## Working-tree safety

The repository may contain user-authored changes. Inspect `git status` before
editing, preserve unrelated modifications, and never discard files to make a
check pass. Destructive Git commands require explicit user approval.

## Definition of done

Work is complete only when the relevant lint, typecheck, tests, and build pass;
the diff contains no unrelated generated files; configuration/documentation is
updated when commands or behavior change; and remaining risks are reported.
