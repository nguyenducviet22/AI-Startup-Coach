# Backend agent guide

These instructions apply to files under `app/` and complement the repository
guide in the root `AGENTS.md`.

## Architecture

- `api/` owns HTTP routing, request/response handling, and dependency injection.
- `services/` owns use cases and orchestration; keep route handlers thin.
- `models/` contains persistence models and shared data structures.
- `domain/` contains deterministic startup-stage concepts and rules.
- `tools/` defines validated operations exposed to the coaching orchestrator.
- `llm/` isolates the OpenAI-compatible provider boundary.

## Non-negotiables

- Use async SQLAlchemy sessions consistently; do not introduce blocking database calls.
- Validate IDs, stage transitions, tool arguments, and provider responses at boundaries.
- Keep secrets out of logs, exceptions, fixtures, and committed configuration.
- Preserve service-level authorization checks when adding new API access paths.
- Prefer explicit typed schemas over unstructured dictionaries at public boundaries.
- Add a new Alembic revision for schema changes and include migration tests where practical.

## Verification

Run `python -m ruff check app tests evals` and the narrowest relevant pytest
module. Run `python -m pytest` for cross-cutting service, API, auth, or persistence
changes, and `python -m evals.run` when coaching behavior or tools change.
