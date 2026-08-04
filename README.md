# AI Startup Coaching Agent

AI Startup Coaching Agent is a full-stack AI product that guides early-stage founders through a structured startup-building journey. Instead of returning a single generic answer, the agent maintains each startup's context, progresses through business-planning stages, uses domain-specific tools to create structured documents, and preserves the evolution of the startup idea over time.

## Why this project

Turning an idea into a startup plan usually requires several disconnected frameworks and repeated manual work. This project combines those workflows into one conversational workspace where founders can move from an initial idea to a practical plan for validation, product development, marketing, and fundraising.

## Key features

- Conversational AI coach with context-aware chat history and startup-specific memory.
- Guided workflow with seven stages: Idea, Lean Canvas, Business Model Canvas, SWOT, Product Plan, Marketing, and Funding.
- Stage-aware tool calling: the model can only access tools that are relevant to the current stage, while validation prevents malformed or out-of-order actions.
- Structured startup documents with version history, current-version tracking, document comparison, and editable workspace views.
- Startup overview and consolidated report for reviewing progress and generated outputs.
- Export reports to PDF/DOCX and export a funding pitch outline as a PDF pitch deck.
- Authentication with password hashing, access tokens, refresh tokens, logout, and ownership checks for startup data.
- AgentOps instrumentation for LLM/tool latency, token usage, estimated cost, errors, and threshold-based error alerts.
- Automated CI/CD with backend and frontend tests, deterministic evaluations, secret scanning, CodeQL, Trivy, and Render deployment hooks.

## Architecture

```text
React + Vite frontend
        |
        | REST API
        v
FastAPI backend
  ├── Authentication and ownership layer
  ├── Agent orchestrator
  │     ├── Context builder
  │     ├── Stage manager
  │     ├── Skill loader
  │     └── Tool dispatcher
  ├── Document, report, and export services
  └── AgentOps instrumentation
        |
        +── PostgreSQL + Alembic migrations
        +── OpenAI-compatible LLM provider (OpenRouter/9Router)
```

The core agent loop is:

```text
User message
  -> load startup context and recent history
  -> load stage-specific skill and tools
  -> call the LLM
  -> validate and execute tool calls
  -> persist documents and conversation events
  -> return the final response and readiness information
```

The agent does not silently advance a startup to the next stage. It checks readiness and asks for confirmation, while users can revisit earlier stages and retain document versions.

## Tech stack

### Frontend

- React 19, TypeScript, Vite
- TanStack Query for server state
- Zustand for local UI/auth state
- React Markdown with GitHub Flavored Markdown support
- Vitest and Testing Library

### Backend

- Python 3.11+, FastAPI, Uvicorn
- SQLAlchemy async ORM with asyncpg
- PostgreSQL and Alembic
- Pydantic Settings for configuration
- OpenAI-compatible chat completion client
- Argon2 password hashing and JWT authentication
- ReportLab and python-docx for document export
- Pytest, HTTPX, and deterministic evaluation fixtures

### Infrastructure and quality

- Docker Compose for local frontend, backend, and PostgreSQL development
- Render Blueprint for deployment
- GitHub Actions for tests, build checks, security scans, and deployment gates

## Project structure

```text
app/        FastAPI application, domain logic, services, models, migrations
frontend/   React application and feature-oriented UI components
skills/     Domain prompts for each startup coaching stage
tests/      Backend unit/integration tests and tool validation tests
evals/      Deterministic, DB-free agent behavior evaluations
docs/       Product specifications, architecture decisions, and handoff notes
```

## Run locally with Docker Compose

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Configure the database and an OpenAI-compatible LLM endpoint in `.env`. For a local 9Router setup, use `http://localhost:20128/v1` as `LLM_BASE_URL`.

3. Start the stack:

   ```bash
   docker compose -f compose.yaml up --build
   ```

4. Open the frontend at `http://localhost:5173`. The backend health endpoint is available at `http://localhost:8000/health`, and FastAPI documentation is available at `http://localhost:8000/docs`.

## Run without Docker

Backend:

```bash
python -m venv .venv
# Activate the virtual environment using the command for your shell.
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## Test and build

```bash
python -m pytest
python -m evals.run

cd frontend
npm run typecheck
npm test
npm run build
```

## Engineering highlights

- Separates API, orchestration, domain, persistence, export, and observability responsibilities into testable services.
- Uses explicit stage schemas and tool validation to make LLM-driven mutations safer and more predictable.
- Keeps generated document history instead of overwriting previous work, making the startup journey auditable.
- Treats observability as part of the agent design by recording turn, LLM, and tool-level metrics.
- Includes automated security gates for secrets, static analysis, and dependency/configuration vulnerabilities.

## Project status

This is an actively developed portfolio project. The repository contains the working application architecture, local Docker workflow, test/evaluation suite, and deployment configuration. Provider credentials and deployment secrets are intentionally supplied through environment variables and are not committed to the repository.

## Author

Nguyen Duc Viet
GitHub: [AI-Startup-Coach](https://github.com/nguyenducviet22/AI-Startup-Coach)
