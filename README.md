# AI Startup Coach

AI Startup Coach is a full-stack coaching workspace that helps founders move
from an idea through structured startup stages, generated documents, reports,
and pitch preparation. The backend combines deterministic domain tools with an
OpenAI-compatible LLM provider; the frontend presents the coaching journey as a
React application.

## Architecture

- `app/`: FastAPI API, async SQLAlchemy persistence, coaching orchestration,
  startup-stage tools, document generation, and LLM integration.
- `frontend/`: React 19, TypeScript, Vite, React Query, and Zustand application.
- `tests/`: backend unit, service, API, persistence, and security tests.
- `evals/`: database-free deterministic coaching evaluations.
- `app/db/migrations/`: PostgreSQL schema migrations managed by Alembic.
- `docs/`: product specifications, plans, deployment notes, and handoffs.

Agent-specific project conventions live in `AGENTS.md` and the scoped guides in
`app/AGENTS.md` and `frontend/AGENTS.md`.

## Configuration

Copy `.env.example` to `.env` and configure at least the database, authentication,
and LLM provider values documented in that file. The primary LLM variables are:

- `LLM_BASE_URL`, such as `http://localhost:20128/v1` for local 9Router.
- `LLM_API_KEY`, which may be empty only when the local provider does not enforce keys.
- `LLM_MODEL`, such as `openai/gpt-4o-mini`.

Legacy `LLM_PROXY_*` and `OPENROUTER_*` variables are temporary fallbacks; new
configuration should use `LLM_*`.

## Backend development

Python 3.11 or newer and PostgreSQL are required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Quality checks:

```bash
python -m ruff check app tests evals
python -m pytest
python -m evals.run
```

Use `python -m ruff format app tests evals` when deliberately formatting the
Python codebase; formatting is not yet a repository-wide legacy-code gate.

Tests that exercise persistence use Testcontainers and therefore require a
working Docker daemon.

## Frontend development

Node.js 22 is the CI-supported runtime.

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Quality checks:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

Set `VITE_API_PROXY_TARGET` when the backend is not available at
`http://localhost:8000`.

## Pre-commit checks

After installing backend development dependencies, enable the repository hooks:

```bash
pre-commit install
pre-commit run --all-files
```

The hooks run Ruff on staged Python files and Biome lint on frontend JavaScript
and TypeScript changes. CI repeats lint, tests, type checking, builds, deterministic
evaluations, secret scanning, CodeQL, and Trivy checks.

## Containers and deployment

`docker compose up --build` starts the containerized stack. Production deployment
is performed by the GitHub Actions workflows after their test and security gates
pass; deployment details are in `docs/render-deployment.md`.
